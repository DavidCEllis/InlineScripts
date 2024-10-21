# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "uv>=0.4.20",
#     "packaging>=24.1",
# ]
# ///
"""
A simple test running script that will create temporary virtual environments for specified
python versions and run the tests in the working directory against them.

Uses UV to create the directories

If an error occurs in testing the result code returned will be the largest error code
thrown by any pytest run.
"""
import os
import sys

import argparse
import contextlib
import enum
import json
import re
import subprocess
import tempfile
import tomllib
import typing

from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version
import uv


if sys.platform == "win32":
    PYTHON_EXE = r"Scripts\python.exe"
else:
    PYTHON_EXE = "bin/python"


UV_PATH = uv.find_uv_bin()


class PyTestExit(enum.IntEnum):
    SUCCESS = 0
    TEST_FAILURES = 1
    TESTS_CANCELLED = 2
    INTERNAL_ERROR = 3
    CMD_ERROR = 4
    NO_TESTS = 5
    NO_ENVS = 404  # Custom error for no environments


class PythonVEnv(typing.NamedTuple):
    exe: Path
    dependencies: set[str]


def call_uv(*args, quiet_uv=False):
    uv_cmd = [UV_PATH, "--quiet"] if quiet_uv else [UV_PATH]
    subprocess.run([*uv_cmd, *args], check=True)


def get_available_pythons(all_versions: bool = False) -> list[str]:
    """
    Get all python install version numbers available from UV

    :param all_versions: Include every patch release and not just the latest
    :return: list of version strings
    """
    # CPython installs listed by UV
    version_re = re.compile(
        r"(?m)^cpython-(?P<version>\d+.\d+.\d+(?:a|b|rc)?\d*).*$"
    )

    cmd = [UV_PATH, "python", "list"]
    if all_versions:
        cmd.append("--all-versions")

    # If pyenv is on `PATH` uv python list is ultra slow
    # So we hide pyenv to make this faster
    env = os.environ.copy()
    pyenv_root = env.get("PYENV_ROOT")
    if pyenv_root:
        path = env["PATH"]
        sep = ";" if sys.platform == "win32" else ":"
        new_path = sep.join(
            p for p in path.split(sep)
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

    return matches


def get_viable_pythons(
    all_versions: bool = False,
    prereleases: bool = False
) -> list[str]:
    # Try to get a requires-python value
    base_path = Path.cwd()
    toml_file = base_path / "pyproject.toml"

    if not toml_file.exists():
        raise RuntimeError(f"No pyproject.toml file found at \"{base_path}\"")

    pyproject = tomllib.loads(toml_file.read_text())

    try:
        requires_python = pyproject["project"]["requires-python"]
    except KeyError:
        raise RuntimeError(
            f"Module folder \"{base_path}\" must have a pyproject.toml "
            f"file with a 'project.requires-python' key"
        )

    spec = SpecifierSet(requires_python)

    if all_versions:
        version_list = sorted(
            {
                p for p in get_available_pythons(all_versions=all_versions)
                if spec.contains(p, prereleases=prereleases)
            },
            key=lambda v: Version(v),
        )
    else:
        # Avoid including multiple micro releases, only use latest
        py_versions = {}
        for p in get_available_pythons(all_versions=all_versions):
            if spec.contains(p, prereleases=prereleases):
                ver = Version(p)
                big_ver = f"{ver.major}.{ver.minor}"
                if current_ver := py_versions.get(big_ver):
                    if ver > current_ver:
                        py_versions[big_ver] = ver
                else:
                    py_versions[big_ver] = ver

        version_list = [str(v) for v in sorted(py_versions.values())]

    return version_list


@contextlib.contextmanager
def build_test_envs(
    pythons: list[str],
    extras: list[str],
    test_path: Path,
    quiet_uv: bool,
) -> list[PythonVEnv]:

    installs: list[PythonVEnv] = []

    extra_str = f"[{','.join(extras)}]" if extras else ""

    with tempfile.TemporaryDirectory(dir=test_path) as tempdir:
        for py_ver in pythons:
            env_folder = Path(tempdir) / py_ver.replace(".", "_")
            # Create venv
            call_uv("venv", "--python", py_ver, env_folder, quiet_uv=quiet_uv)

            # Install dependencies with extras if given
            call_uv(
                "pip", "install",
                "--python", env_folder,
                "-e", f".{extra_str}",
                quiet_uv=quiet_uv
            )

            try:
                pip_list = subprocess.run(
                    [
                        UV_PATH, "pip", "list",
                        "--python", env_folder,
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
                call_uv("pip", "install", "--python", env_folder, "pytest", quiet_uv=quiet_uv)

            python_path = Path(env_folder) / PYTHON_EXE
            assert python_path.exists()

            installs.append(PythonVEnv(python_path, dependency_set))
        yield installs


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
        help="Don't display UV output, always on if running parallel tests"
    )
    parser.add_argument(
        "++prereleases",
        action="store_true",
        help="Test against available pre-release Python versions"
    )
    parser.add_argument(
        "++parallel",
        action="store_true",
        help=(
            "Run tests for each Python version in parallel "
            "(This does not run individual tests in parallel! "
            "Still has many of the same issues though.)"
        )
    )

    return parser


def main() -> PyTestExit:
    parser = get_parser()
    test_args, pytest_args = parser.parse_known_args()

    pythons = get_viable_pythons(
        all_versions=False,
        prereleases=test_args.prereleases,
    )

    cwd = Path.cwd()
    test_path = cwd / "env_testing"
    test_path.mkdir(exist_ok=True)

    # Build the temporary environments as a context manager
    with build_test_envs(
        pythons=pythons,
        extras=test_args.extras,
        test_path=test_path,
        quiet_uv=test_args.quiet,
    ) as python_venvs:

        result_codes: list[PyTestExit] = []

        if test_args.parallel:
            # Threads are appropriate as subprocess does not hold the GIL
            from concurrent.futures import ThreadPoolExecutor, as_completed
            try:
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
            finally:
                try:
                    test_path.rmdir()
                except OSError:
                    pass

        else:
            try:
                for venv in python_venvs:
                    result = run_tests_in_version(
                        venv=venv,
                        pytest_args=pytest_args,
                        no_coverage=False,
                    )
                    result_codes.append(PyTestExit(result.returncode))
            finally:
                try:
                    test_path.rmdir()
                except OSError:
                    pass

    if not result_codes:
        return PyTestExit.NO_ENVS
    else:
        return max(PyTestExit.SUCCESS, *result_codes)


if __name__ == "__main__":
    exit_code = main().value
    sys.exit(exit_code)
