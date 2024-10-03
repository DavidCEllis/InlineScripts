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
