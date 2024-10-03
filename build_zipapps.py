import os
import os.path
import sys

import subprocess
from pathlib import Path


def make_zipapps(zipapp_dir: Path):
    base_dir = Path(__file__).parent

    script_dir = base_dir / "scripts"

    ducktools_env = base_dir / "ducktools.pyz"

    for p in script_dir.glob("*.py"):
        out_p = zipapp_dir / p.with_suffix(".pyz").name

        subprocess.run(
            [
                sys.executable,
                str(ducktools_env),
                "bundle", str(p),
                "-o", str(out_p),
            ]
        )


def main():
    if sys.platform == "win32":
        zipapp_dir = Path(os.environ["USERPROFILE"]) / "bin"
    else:
        zipapp_dir = Path(os.path.expanduser("~")) / "bin"

    make_zipapps(zipapp_dir)


if __name__ == "__main__":
    main()
