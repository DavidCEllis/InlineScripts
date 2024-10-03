import sys

import subprocess
from pathlib import Path


def main():
    base_dir = Path(__file__).parent

    script_dir = base_dir / "scripts"
    zipapp_dir = base_dir / "zipapps"

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


if __name__ == "__main__":
    main()
