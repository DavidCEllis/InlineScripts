# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "uv>=0.4.20",
#     "packaging>=24.1",
# ]
# ///
"""
Build virtual environments with the relevant python versions supported by a module
"""
import sys

import argparse
import os
import re
import shutil
import subprocess
import tomllib

from pathlib import Path

import uv
from packaging.specifiers import SpecifierSet
from packaging.version import Version


UV_PATH = uv.find_uv_bin()
VENV_BASE = ".venv"


def call_uv(*args, quiet_uv=False):
    uv_cmd = [UV_PATH, "--quiet"] if quiet_uv else [UV_PATH]
    subprocess.run([*uv_cmd, *args], check=True)


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

    return parser


def get_available_pythons(all_versions: bool = False) -> list[str]:
    """
    Get all python install version numbers available from UV

    :param all_versions: Include every patch release and not just the latest
    :return: list of version strings
    """
    # CPython installs listed by UV - only want downloadable installs
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


def get_matching_python(spec: SpecifierSet, versions: list[str], mode: str) -> str:
    viable_versions = [s for s in versions if spec.contains(s)]
    match mode:
        case "oldest":
            return min(viable_versions, key=Version)
        case "newest":
            return max(viable_versions, key=Version)
        case _:
            raise RuntimeError(f"Mode can only be 'oldest' or 'newest', given {mode!r}")


def build_env(
    project_path: Path,
    pythons: list[str],
    mode: str,
    extras: list[str],
    clear_existing: bool = True
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

    if usable_extras:
        extras_str = "[" + ", ".join(usable_extras) + "]"
    else:
        extras_str = ""

    spec = SpecifierSet(requires_python)
    base_python = get_matching_python(spec, pythons, mode)

    venv_cmd = ["uv", "venv", str(venv_folder), "--python", base_python]

    subprocess.run(venv_cmd, check=True)

    pip_command = [
        "uv", "pip", "install",
        "-e", f".{extras_str}",
        "--python", str(venv_folder),
    ]

    subprocess.run(pip_command, check=True)

    print(f"Built environment in \"{venv_folder}\"")


def build_envs(
    mode: str,
    extras: list[str],
    subfolders: bool = False
) -> None:
    pythons = get_available_pythons(all_versions=False)

    if not subfolders:
        project_path = Path.cwd()
        build_env(project_path, pythons, mode, extras)
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


def main():
    parser = build_parser()
    args = parser.parse_args()

    build_envs(
        mode=args.mode,
        extras=args.extras,
        subfolders=args.subfolders
    )
