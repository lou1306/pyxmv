# `pyxmv` - (Unofficial) Python interface to nuXmv

[nuXmv](https://nuxmv.fbk.eu/) is a state-of-the-art symbolic model checker for
the analysis of finite- and infinite- state systems

`pyxmv` is a (very much WIP) wrapper for the nuXmv command-line interface; it
aims at providing APIs for several features, and comes with a small CLI to
showcase what it can do.

The CLI itself should, in time, become an alternative to the official one with
a focus on automation/scriptability/interop with other
tools/pipelines/workflows.

# Quickstart

Besides nuXmv, the tool requires Python >= 3.9 and Poetry.

After cloning this repository:

```bash
cd pyxmv
poetry update
poetry run pyxmv --help
# Optionally, install in your current Python environment
poetry install
```

# Future work

* Parse simulation traces into structured data for easier interop

* Support alternative simulation heuristics

* Support NuSMV

# Licensing caveats

`pyxmv` is MIT-licensed, but it is perfectly useless unless you obtain a copy
of nuXmv. Licensing restrictions forbid me from redistributing it, but it may
be downloaded [here](https://nuxmv.fbk.eu/download.html)
