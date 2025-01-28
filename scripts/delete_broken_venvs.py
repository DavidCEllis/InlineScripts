# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "ducktools-pythonfinder>=0.7.2",
# ]
# ///


"""
A Simple script to search for and clear out 'broken' virtual environments
"""
import shutil
import argparse
from pathlib import Path

from ducktools.pythonfinder.venv import get_python_venvs


CWD = Path.cwd()


def delete_broken_venvs(base_dir=CWD, delete_envs=False):
    """
    Search from base_dir recursively looking for Python venvs.
    If an invalid venv is discovered, list and optionally delete it.

    :param base_dir: Base directory from which to start searching
    :param delete_envs: Delete discovered invalid envs
    """

    for env in get_python_venvs(base_dir=base_dir, recursive=True):
        if not env.parent_exists:
            fld_str = str(Path(env.folder).relative_to(base_dir))
            if delete_envs:
                print(f"Deleting: {fld_str}")
                shutil.rmtree(env.folder)
            else:
                print(fld_str)


def get_parser():
    parser = argparse.ArgumentParser(
        description="Search for and Delete Broken Python Virtual Environments"
    )

    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete broken venv folders as they are discovered."
    )

    parser.add_argument(
        "--folder",
        action="store",
        help="Select alternative folder, default is CWD"
    )

    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    base_dir = (
        CWD if args.folder is None
        else Path(args.folder).resolve().relative_to(CWD, walk_up=True)
    )
    delete_broken_venvs(base_dir=base_dir, delete_envs=args.delete)


if __name__ == "__main__":
    main()
