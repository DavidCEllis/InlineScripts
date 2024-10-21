# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "ducktools-pythonfinder>=0.6.0",
#   "packaging>=24.1"
# ]
# ///
import sys

if sys.platform != "win32":
    print("Script is for Windows Only")
    sys.exit()

import argparse
import os.path

from ducktools.pythonfinder.shared import get_uv_pythons, PythonInstall
from packaging.version import Version


COMPANY = "uv"
COMPANY_NAME = "Astral"
SUPPORT_URL = "https://astral.sh/uv"


def get_version_details(p: PythonInstall):
    v = p.version
    if p.implementation == "cpython":
        tag = f"{v[0]}.{v[1]}"
        display_name = f"Python {p.version_str} ({p.architecture})"
    else:
        # Still use the language version as the tag
        tag = f"{p.implementation}{v[0]}.{v[1]}"
        display_name = f"{p.implementation} {p.implementation_version_str} ({p.architecture})"

    windowed_path = "w".join(os.path.splitext(p.executable))
    details = (
        tag,
        {
            "DisplayName": display_name,
            "SupportUrl": SUPPORT_URL,
            "Version": p.implementation_version_str,
            "SysVersion": p.version_str,
            "SysArchitecture": p.architecture,
            "InstallPath": {
                "ExecutablePath": p.executable,
                "WindowedExecutablePath": windowed_path,
            },
        },
    )

    return details


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove all UV pythons from the Windows registry"
    )


def main():
    for p in get_uv_pythons():
         print(get_version_details(p))


if __name__ == "__main__":
    main()
