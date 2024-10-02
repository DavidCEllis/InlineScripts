# /// script
# requires-python = "~=3.12.5"
# dependencies = [
#     "mutagen>=1.47",
#     "rich>=13.9",
#     "ducktools-classbuilder>=0.7.2",
# ]
# ///

"""
I have a collection of MP3 files, but some were ripped a long time ago at a low bitrate.

This is a simple script to find these files
"""

from collections.abc import Generator
from pathlib import Path
from argparse import ArgumentParser

from ducktools.classbuilder.prefab import Prefab  # noqa
from mutagen.easyid3 import EasyID3  # noqa
from mutagen.mp3 import MP3  # noqa
from rich import print as rprint  # noqa
from rich.console import Console  # noqa
from rich.table import Table  # noqa


class MP3File(Prefab):
    path: Path
    artist: str | None
    album: str | None
    bitrate: int


def find_bad_mp3s(
    base_path: Path,
    minimum_bitrate: int = 192,
) -> Generator[MP3File]:
    """
    Search for MP3s with bitrate lower than a given bitrate
    :param base_path: Base path to search for MP3s
    :param minimum_bitrate: Bitrate in kbps
    :return: Mp3 file and bitrate
    """
    mp3_list = list(base_path.rglob(f"*.mp3", case_sensitive=False))
    minimum_bitrate = minimum_bitrate * 1000

    for p in mp3_list:
        audio = MP3(p, ID3=EasyID3)
        mp3_bitrate = audio.info.bitrate
        if mp3_bitrate < minimum_bitrate:
            artist = audio.tags.get("artist")
            album = audio.tags.get("album")
            artist = artist[0] if isinstance(artist, list) else artist
            album = album[0] if isinstance(album, list) else album

            yield MP3File(p, artist, album, mp3_bitrate // 1000)


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "base_path",
        help="Base folder to use for MP3 search",
        nargs="?",
        default=None,
    )

    parser.add_argument(
        "--bitrate",
        help="minimum bitrate in kbps",
        type=int,
        default=192,
    )

    args = parser.parse_args()

    base_path = Path(args.base_path) if args.base_path else Path.cwd()

    rprint(f"Searching {base_path}")

    table = Table(title="Low Bitrate Albums")
    table.add_column("Artist", justify="left")
    table.add_column("Album", justify="left")
    table.add_column("Bitrate", justify="right")

    unknown_table = Table(title="Low Bitrate Misc")
    unknown_table.add_column("Path")
    unknown_table.add_column("Bitrate")

    albums_included = set()
    for f in find_bad_mp3s(base_path, args.bitrate):
        if not (f.artist and f.album):
            unknown_table.add_row(str(f.path), str(f.bitrate))
        else:
            album_artist = (f.artist, f.album)
            if album_artist in albums_included:
                continue
            albums_included.add(album_artist)
            table.add_row(f.artist, f.album, str(f.bitrate))

    console = Console()
    if table.rows:
        console.print(table)
    if unknown_table.rows:
        console.print(unknown_table)


if __name__ == "__main__":
    main()
