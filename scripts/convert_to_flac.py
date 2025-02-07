# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "tqdm",
# ]
# ///

# Convert audio files to flac

import argparse
import subprocess
from pathlib import Path

from contextlib import contextmanager
from tkinter import Tk, filedialog

from tqdm import tqdm

@contextmanager
def handle_tk_root():
    """
    Short decorator to create, hide and destroy the necessary Tk root

    Using tkinter directly without defining the root first leaves a small
    blank window. This hides the window.
    """
    root = Tk()
    root.withdraw()
    try:
        yield
    finally:
        root.destroy()


@handle_tk_root()
def askopenfilename(**options):
    """
    Passes to askopenfilenname

    :param options: askopenfilename options (see tkinter docs)
    :return: Path of filename or None
    """
    open_filename = filedialog.askopenfilename(**options)

    if open_filename:
        return Path(open_filename)
    else:
        return None


@handle_tk_root()
def askopenfilenames(*, sort_files=False, **options):
    """
    Passes to askopenfilenames

    :param sort_files: sort the filenames alphabetically before returning
    :param options: askopenfilennames options (see tkinter docs)
    :return: List of Paths of filenames or None
    """
    open_filenames = filedialog.askopenfilenames(**options)

    if open_filenames:
        if sort_files:
            open_filenames = sorted(open_filenames)
        return [Path(f) for f in open_filenames]
    else:
        return None


@handle_tk_root()
def asksaveasfilename(**options):
    """
    Passes to asksaveasfilename

    :param options: asksaveasfilename options (see tkinter docs)
    :return: Path of filename or None
    """
    save_filename = filedialog.asksaveasfilename(**options)

    if save_filename:
        return Path(save_filename)
    else:
        return None


@handle_tk_root()
def askdirectory(**options):
    """
    Passes to askdirectory

    :param options: askdirectory optionns (see tkinter docs)
    :return: Path of directory or None
    """
    directory = filedialog.askdirectory(**options)
    if directory:
        return Path(directory)
    else:
        return None



def convert_folder(src, dest, bitdepth=16, samplerate=48000, input_fmt="wav"):
    src_path = Path(src)
    dest_path = Path(dest)
    sources = list(src_path.glob("**/*.wav"))

    for i, f in enumerate(tqdm(sources)):
        f_dest = (dest_path / f.relative_to(src_path)).with_suffix(".flac")
        f_dest.parent.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            [
                "ffmpeg",
                "-i", f,
                "-resampler", "soxr",
                "-ar", str(samplerate),
                "-sample_fmt", f"s{bitdepth}",
                f_dest,
            ],
            capture_output=True,
            check=True,
        )


def get_parser():
    parser = argparse.ArgumentParser(description="Convert audio to flac with given bit depth and sample rate")
    parser.add_argument("source", action="store", help="Folder with source audio files")
    parser.add_argument("--dest", action="store", help="Destination Folder", default=None)
    parser.add_argument("--samplerate", action="store", default=48000, type=int, help="Sample Rate")
    parser.add_argument("--bitdepth", action="store", default=16, type=int, help="Bit Depth")
    parser.add_argument("--inputformat", action="store", default="wav", help="Format of the input file (default: wav)")

    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    if (dest := args.dest) is None:
        dest = askdirectory()

    convert_folder(args.source, dest, args.bitdepth, args.samplerate, args.inputformat)


if __name__ == "__main__":
    main()
