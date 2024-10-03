# Inline Scripts #

A collection of scripts for various tasks that use Python 
[Inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/#inline-script-metadata)
to declare dependencies as originally specified in PEP-723.

## How to use .py scripts ##

These scripts are designed to be used with an inline dependency script runner.

The `build_zipapps.py` script requires `uv` be installed on `PATH` and will generate
bundled zipapps with [ducktools-env](https://github.com/DavidCEllis/ducktools-env) that
can be used from any Python install of 3.10 or later.

It puts the scripts in `~/bin` on Linux/MacOs and `%USERPROFILE%\bin` on Windows.

## Included Scripts ##

These scripts are just a random collection of tools I find useful

* run_tests
  * A script that will run pytest in the current folder for the latest patch of every 
    minor Python release available via `uv` that satisfies `requires-python` in the 
    current path's pyproject.toml
* find_low_bitrate_music
  * Finds and lists any albums of MP3 tracks that were ripped below a specified bitrate
    (If only I'd ripped everything to flac years ago)
