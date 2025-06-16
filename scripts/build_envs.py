# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "packaging>=24.1",
#     "ducktools-pythonfinder>=0.6.7",
# ]
# ///
"""
Build virtual environments with the relevant python versions supported by a module.
It should always use the newest patch of whichever version it is installing.
"""
import argparse
import shutil
import subprocess
import tomllib

from pathlib import Path

from ducktools.pythonfinder import list_python_installs, PythonInstall
from packaging.specifiers import SpecifierSet
from packaging.version import Version


VENV_BASE = ".venv"
UV_PATH = shutil.which("uv")

if UV_PATH is None:
    raise FileNotFoundError(
        "Could not find the path to the 'uv' binary, make sure 'uv' is installed and available on PATH"
    )


def call_uv(*args, quiet_uv=False):
    uv_cmd = [UV_PATH, "--quiet"] if quiet_uv else [UV_PATH]
    subprocess.run([*uv_cmd, *args], check=True)


def get_matching_python(
    spec: SpecifierSet,
    versions: list[PythonInstall],
    mode: str,
) -> PythonInstall:
    viable_versions = [s for s in versions if spec.contains(s.version_str)]
    
    if not viable_versions:
        raise RuntimeError(f"Could not find a matching python version for {spec}")

    def install_version(install):
        return Version(install.version_str)

    match mode:
        case "oldest":
            return min(viable_versions, key=install_version)
        case "newest":
            return max(viable_versions, key=install_version)
        case _:
            raise RuntimeError(f"Mode can only be 'oldest' or 'newest', given {mode!r}")


def build_env(
    project_path: Path,
    pythons: list[str],
    mode: str,
    extras: list[str],
    prereleases: bool = False,
    clear_existing: bool = True,
) -> None:
    toml_file = project_path / "pyproject.toml"
    venv_folder = project_path / VENV_BASE

    if clear_existing:
        shutil.rmtree(venv_folder, ignore_errors=True)
    elif venv_folder.exists():
        raise FileExistsError(f".venv folder \"{venv_folder}\" already exists")

    if not toml_file.exists():
        raise FileNotFoundError(f"No pyproject.toml file found at \"{project_path}\"")

    pyproject = tomllib.loads(toml_file.read_text())

    try:
        requires_python = pyproject["project"]["requires-python"]
    except KeyError:
        raise RuntimeError(
            f"Module folder \"{project_path}\" must have a 'pyproject.toml' "
            f"file with a 'project.requires-python' key"
        )

    # Check for extras
    usable_extras = []
    try:
        extra_keys = pyproject["project"]["optional-dependencies"].keys()
    except KeyError:
        pass
    else:
        # Usable extras are those given and defined - use intersection
        usable_extras.extend(set(extras) & extra_keys)

    spec = SpecifierSet(requires_python, prereleases=prereleases)
    base_python = get_matching_python(spec, pythons, mode)

    # Sync the venv with UV
    sync_command = [
        UV_PATH, "sync",
        "--directory", str(project_path),
        "--python", base_python.executable,
    ]

    for extra in usable_extras:
        sync_command.extend(["--extra", extra])

    subprocess.run(sync_command, check=True)

    print(f"Built environment in \"{venv_folder}\"")


def build_envs(
    mode: str,
    extras: list[str],
    subfolders: bool = False,
    prereleases: bool = False,
) -> None:
    pythons = []
    major_pythons = set()

    for inst in list_python_installs():
        if inst.implementation != "cpython":
            continue
        if inst.version[:2] in major_pythons:
            continue
        major_pythons.add(inst.version[:2])
        pythons.append(inst)

    if not subfolders:
        project_path = Path.cwd()
        build_env(project_path, pythons, mode, extras, prereleases=prereleases)
    else:
        base_project_paths = Path.cwd().glob("*/")
        for p in base_project_paths:
            toml_path = p / "pyproject.toml"
            # Skip folders without pyproject.toml files
            if not toml_path.exists():
                continue
            try:
                build_env(p, pythons, mode, extras)
            except (FileExistsError, RuntimeError) as e:
                print(e)
                continue


def build_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mode",
        choices=["oldest", "newest"],
        default="oldest",
        help=(
            "Create venvs with the oldest or newest Python version "
            "supported by the project. "
            "Defaults to oldest."
        )
    )

    parser.add_argument(
        "--subfolders",
        action="store_true",
        help="Search through subfolders and update envs for projects discovered"
    )

    parser.add_argument(
        "-e", "--extra",
        action="append",
        default=[],
        help="Add extras if present in the base environment."
    )

    parser.add_argument(
        "--prereleases",
        action="store_true",
        help="Include prerelease Python versions"
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    build_envs(
        mode=args.mode,
        extras=args.extra,
        subfolders=args.subfolders,
        prereleases=args.prereleases,
    )


if __name__ == "__main__":
    main()
