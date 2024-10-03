# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "uv>=0.4.18",
# ]
# ///
import sys

import argparse
import json
import subprocess
import tempfile

from pathlib import Path

if sys.platform == "win32":
    PYTHON_EXE = r"Scripts\python.exe"
else:
    PYTHON_EXE = "bin/python"


def uv(*args, quiet_uv=False):
    # Call UV from python to ensure it is the one requested
    uv_cmd = [sys.executable, "-m", "uv", "--quiet"] if quiet_uv else [sys.executable, "-m", "uv"]
    subprocess.run([*uv_cmd, *args], check=True)


def run_tests_in_version(py_ver: str, package: str, pytest_args: list[str], quiet_uv=False):
    cwd = Path.cwd()
    test_path = cwd / "env_testing"
    test_path.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(
        dir=test_path,
        prefix=f"{py_ver.replace('.', '_')}_",
    ) as tempdir:
        # Create venv and install package
        uv("venv", "--python", py_ver, tempdir, quiet_uv=quiet_uv)

        # Install package as editable so coverage works
        uv("pip", "install", "--python", tempdir, "-e", package, quiet_uv=quiet_uv)

        # Check if pytest is installed, if not, install it
        pip_list = subprocess.run(
            [
                sys.executable, "-m",
                "uv", "pip", "list",
                "--python", tempdir,
                "--format", "json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        dependency_set = {p["name"] for p in json.loads(pip_list.stdout)}
        if "pytest" not in dependency_set:
            uv("pip", "install", "--python", tempdir, "pytest", quiet_uv=quiet_uv)

        python_path = Path(tempdir) / PYTHON_EXE
        assert python_path.exists()

        subprocess.run(
            [str(python_path), "-m", "pytest", *pytest_args]
        )

    # delete the env_testing directory if it is empty
    try:
        test_path.rmdir()
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser(prefix_chars="+")
    parser.add_argument(
        "+p", "++python",
        action="append",
        default=None,
        help="Python version number. If multiple are specified run against each."
    )
    parser.add_argument(
        "+m", "++module",
        action="store",
        default=".",
        help="Path to base module for pip install, include extras if necessary",
    )
    parser.add_argument(
        "+q", "++quiet",
        action="store_true",
        help="Don't display UV output"
    )

    test_args, pytest_args = parser.parse_known_args()

    if test_args.python is None:
        v = sys.version_info
        pythons = [f"{v.major}.{v.minor}"]
    else:
        pythons = test_args.python

    for python in pythons:
        run_tests_in_version(
            py_ver=python,
            package=test_args.module,
            pytest_args=pytest_args,
            quiet_uv=test_args.quiet,
        )


if __name__ == "__main__":
    main()
