# Inline Scripts #

A collection of scripts for various tasks that use Python 
[Inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/#inline-script-metadata)
to declare dependencies as originally specified in PEP-723.

## How to use .py scripts ##

These scripts are designed to be used with an inline dependency script runner.

If you use `uv` these can be launched with: `uv run scriptname.py`

If you use `ducktools-env` these can be launched with `dtrun scriptname.py`
or registered with `ducktools-env register scriptname.py` and subsequently
run with `dtrun scriptname` (without .py) from any folder.

For example.

Register the script under an alias:
`ducktools-env register -n brokenvs delete_broken_venvs.py `

List registered Scripts:
`ducktools-env list --scripts`

Launch the registered script using its alias:
`dtrun brokenvs`

## Included Scripts ##

These scripts are just a random collection of tools I find useful

* build_envs
  * Create a venv with an appropriate python version for the current 
    project folder and install the project dependencies into it
* delete_broken_venvs
  * Search a folder and any subfolders for Python virtual environments
  * List any that are found where the parent python runtime no longer exists
  * Optionally delete these VEnvs automatically
* pylauncher
  * Open up a gui launcher to launch a REPL from any python install that
    `ducktools-pythonfinder` can discover
  * This may be turned into a more complete application at some point
* run_tests
  * A script that will run pytest in the current folder for the latest patch of every 
    minor Python release available via `uv` that satisfies `requires-python` in the 
    current path's pyproject.toml
* find_low_bitrate_music
  * Finds and lists any albums of MP3 tracks that were ripped below a specified bitrate
    (If only I'd ripped everything to flac years ago)
