# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "packaging>=24.1",
#     "ducktools-pythonfinder>=0.6.0",
#     "ducktools-classbuilder>=0.7.2",
# ]
# ///
"""
Run the tests in multiple isolated UV environments
"""
import os
import sys

import argparse
import enum
import json
import operator
import re
import shutil
import subprocess
import tomllib

from pathlib import Path
from collections.abc import Generator

from ducktools.classbuilder.prefab import Prefab
from ducktools.pythonfinder import get_python_installs, PythonInstall
from packaging.specifiers import SpecifierSet
from packaging.version import Version


if sys.platform == "win32":
    PYTHON_EXE = r"Scripts\python.exe"
else:
    PYTHON_EXE = "bin/python"


TEST_ENV_FOLDER = ".test_venvs"


UV_PATH = shutil.which("uv")

if UV_PATH is None:
    raise FileNotFoundError(
        "Could not find the path to the 'uv' binary, make sure 'uv' is installed and available on PATH"
    )


class PyTestExit(enum.IntEnum):
    SUCCESS = 0
    TEST_FAILURES = 1
    TESTS_CANCELLED = 2
    INTERNAL_ERROR = 3
    CMD_ERROR = 4
    NO_TESTS = 5
    NO_ENVS = 404  # Custom error for no environments


class PythonVEnv(Prefab):
    exe: Path
    dependencies: set[str]


class ResultData(Prefab):
    venv_path: str
    test_output: subprocess.CompletedProcess


def call_uv(*args, quiet_uv=False, env=None):
    if env is not None:
        sys_env = os.environ.copy()
        sys_env.update(env)
        env = sys_env

    uv_cmd = [UV_PATH, "--quiet"] if quiet_uv else [UV_PATH]
    subprocess.run([*uv_cmd, *args], check=True, env=env)


def implementation_version_tuple(install) -> tuple[str, int, int]:
    return install.implementation, install.version[0], install.version[1]


def get_uv_python_installables() -> list[Version]:
    """
    Get all downloadable UV Pythons that satisfy a spec

    :return: list of valid Versions
    """
    # CPython downloadable installs only
    version_re = re.compile(
        r"(?m)^cpython-(?P<version>\d+.\d+.\d+(?:a|b|rc)?\d*).*<download available>$"
    )

    # If pyenv is on `PATH` uv python list is ultra slow
    # So we hide pyenv to make this faster
    env = os.environ.copy()
    pyenv_root = env.get("PYENV_ROOT")
    if pyenv_root:
        path = env["PATH"]
        new_path = os.pathsep.join(
            p for p in path.split(os.pathsep)
            if not p.startswith(pyenv_root)
        )
        env["PATH"] = new_path

    data = subprocess.run(
        [
            UV_PATH,
            "python",
            "list",
        ],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )

    matches = version_re.findall(data.stdout)

    return [Version(m) for m in matches]


def get_project_specifier(pyproject: dict) -> SpecifierSet:
    try:
        requires_python = pyproject["project"]["requires-python"]
    except KeyError:
        raise RuntimeError(
            "pyproject.toml file must have a 'project.requires-python' key"
        )

    return SpecifierSet(requires_python)


def get_viable_pythons(
    spec: SpecifierSet,
    prereleases: bool = False,
    pypy: bool = False,
    graalpy: bool = False
) -> list[PythonInstall]:

    # Get python installs from the system
    implementations = {"cpython"}
    if pypy:
        implementations.add("pypy")
    if graalpy:
        implementations.add("graalpy")
    
    # The full filter for valid python versions
    def version_filter(install):
        valid_release = (prereleases or install.version[3] == "final")
        valid_implementation = install.implementation in implementations
        satisfies_spec = spec.contains(install.version_str, prereleases=prereleases)

        return valid_release and valid_implementation and satisfies_spec

    pythons: dict[tuple[str, int, int], PythonInstall] = {}

    for p in get_python_installs():
        if not version_filter(p):
            continue
        if current_install := pythons.get(implementation_version_tuple(p)):
            if p.implementation_version <= current_install.implementation_version:
                continue

        pythons[implementation_version_tuple(p)] = p

    return sorted(pythons.values(), key=operator.attrgetter("version"))


def sync_test_envs(
    pythons: list[PythonInstall],
    extras: list[str],
    test_path: Path,
    quiet_uv: bool,
    test_lowest: bool,
) -> Generator[list[PythonVEnv]]:

    installs: list[PythonVEnv] = []

    resolution_modes = ["highest"]
    if test_lowest:
        resolution_modes.append("lowest-direct")

    for py in pythons:
        for mode in resolution_modes:
            # sync environments with both resolution types
    
            env_path = test_path / mode / py.implementation / ".".join(str(v) for v in py.version[:2])
            
            # Make the parent folders if they don't exist
            env_path.parent.mkdir(exist_ok=True, parents=True)
            
            # Sync the environment
            uv_cmd = [
                "sync", 
                "--python", py.executable,
            ]
            for extra in extras:
                uv_cmd.extend(["--extra", extra])

            call_uv(
                *uv_cmd,
                env={
                    "UV_RESOLUTION": mode,
                    "UV_PROJECT_ENVIRONMENT": str(env_path),
                    "UV_FROZEN": "true",
                },
                quiet_uv=quiet_uv,
            )
        
            # Check if pytest is in the environment
            try:
                pip_list = subprocess.run(
                    [
                        UV_PATH, "pip", "list",
                        "--python", str(env_path),
                        "--format", "json",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to list dependencies with UV: {e.stderr}")

            dependency_set = {p["name"] for p in json.loads(pip_list.stdout)}
            if "pytest" not in dependency_set:
                call_uv("pip", "install", "--python", str(env_path), "pytest", quiet_uv=quiet_uv)

            python_path = env_path / PYTHON_EXE
            assert python_path.exists()

            installs.append(PythonVEnv(python_path, dependency_set))

    return installs


def run_tests_in_version(
    venv: PythonVEnv,
    pytest_args: list[str],
    no_coverage: bool = False,
    capture_output: bool = False,
):
    python_path = venv.exe
    dependency_set = venv.dependencies

    cmd = [str(python_path), "-m", "pytest", "--color=yes", *pytest_args]
    if no_coverage and "pytest-cov" in dependency_set:
        cmd.append("--no-cov")

    out = subprocess.run(
        cmd,
        capture_output=capture_output,
    )

    return out


def get_parser():
    parser = argparse.ArgumentParser(prefix_chars="+")
    parser.add_argument(
        "+e", "++extras",
        action="append",
        default=[],
        help="Extras to include for testing (use once per extra)",
    )
    parser.add_argument(
        "+q", "++quiet",
        action="store_true",
        help="Don't display UV output.",
    )
    parser.add_argument(
        "++prereleases",
        action="store_true",
        help="Test against available pre-release Python versions",
    )
    parser.add_argument(
        "++pypy",
        action="store_true",
        help="Include PyPy installs in testing (will not install them if missing).",
    )
    parser.add_argument(
        "++graalpy",
        action="store_true",
        help="Include GraalPy installs in testing (will not install them if missing).",
    )
    parser.add_argument(
        "++install-missing",
        action="store_true",
        help=(
            "Install missing major CPython releases from UV if available. "
            "(This will not update patch releases.)"
        ),
    )
    parser.add_argument(
        "++parallel",
        action="store_true",
        help=(
            "Run tests for each Python version in parallel "
            "(This does not run individual tests in parallel! "
            "Still has many of the same issues though.)"
        ),
    )
    parser.add_argument(
        "++lowest",
        action="store_true",
        help="Also test against the lowest matching versions of dependencies",
    )

    return parser


def main() -> PyTestExit:
    parser = get_parser()
    test_args, pytest_args = parser.parse_known_args()

    cwd = Path.cwd()

    pyproject_path = cwd / "pyproject.toml"

    if not pyproject_path.exists():
        raise RuntimeError(f"No pyproject.toml file found at \"{Path.cwd()}\"")
    
    uv_lock_path = cwd / "uv.lock"
    if not uv_lock_path.exists():
        call_uv("lock")
    
    pyproject_toml = tomllib.loads(pyproject_path.read_text())
    spec = get_project_specifier(pyproject=pyproject_toml)
    
    pythons = get_viable_pythons(
        spec=spec,
        prereleases=test_args.prereleases,
        pypy=test_args.pypy,
        graalpy=test_args.graalpy,
    )

    if test_args.install_missing:
        uv_pythons = get_uv_python_installables()
        python_releases = {p.version[:2] for p in pythons if p.implementation == "cpython"}
        missing_versions = [
            f"{v.major}.{v.minor}" for v in uv_pythons
            if (v.major, v.minor) not in python_releases
            and spec.contains(v)
        ]
        if missing_versions:
            call_uv(
                "python", "install", *missing_versions,
                quiet_uv=test_args.quiet
            )

            # redo the search to pickup the new installs
            pythons = get_viable_pythons(
                spec=spec,
                prereleases=test_args.prereleases,
                pypy=test_args.pypy,
                graalpy=test_args.graalpy,
            )

    test_path = cwd / TEST_ENV_FOLDER
    test_path.mkdir(exist_ok=True)

    # Add a gitignore file if it doesn't exist to ignore the test folder
    test_folder_gitignore = test_path / ".gitignore"
    if not test_folder_gitignore.exists():
        test_folder_gitignore.write_text("*\n")

    # Build the temporary environments as a context manager
    python_venvs = sync_test_envs(
        pythons=pythons,
        extras=test_args.extras,
        test_path=test_path,
        quiet_uv=test_args.quiet,
        test_lowest=test_args.lowest,
    )

    result_codes: list[PyTestExit] = []

    if test_args.parallel:
        # Threads are appropriate as subprocess does not hold the GIL
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor() as pool:
            futures = [
                pool.submit(
                    run_tests_in_version,
                    venv=venv,
                    pytest_args=pytest_args,
                    no_coverage=True,
                    capture_output=True,
                )
                for venv in python_venvs
            ]

            for r in as_completed(futures):
                result = r.result()
                
                result_codes.append(PyTestExit(result.returncode))
                if result.stderr:
                    sys.stderr.buffer.write(result.stderr)
                if result.stdout:
                    sys.stdout.buffer.write(result.stdout)

    else:
        for venv in python_venvs:
            result = run_tests_in_version(
                venv=venv,
                pytest_args=pytest_args,
                no_coverage=False,
            )
            result_codes.append(PyTestExit(result.returncode))

    if not result_codes:
        return PyTestExit.NO_ENVS
    else:
        return max(PyTestExit.SUCCESS, *result_codes)


if __name__ == "__main__":
    exit_code = main().value
    sys.exit(exit_code)
