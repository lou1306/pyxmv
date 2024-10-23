# `pyxmv` - (Unofficial) Python interface to nuXmv

[nuXmv](https://nuxmv.fbk.eu/) is a state-of-the-art symbolic model checker for
the analysis of finite- and infinite- state systems.

`pyxmv` is a (very much WIP) wrapper for the nuXmv command-line interface; it
aims at providing APIs for several features, and comes with a small CLI to
showcase what it can do.

The CLI itself should, in time, become an alternative to the official one with
a focus on automation/scriptability/interop with other
tools/pipelines/workflows.

# Quickstart

Besides nuXmv, the tool requires Python >= 3.10 and Poetry.

After cloning this repository:

```bash
cd pyxmv
poetry update
poetry install
pyxmv --help
```

## Install options

```bash
poetry install --only main  # Only installs packages that pyxmv needs to run
poetry install              # Also install dev dependencies
poetry install --all-extras # Installs all optional packages
```

Dev dependencies are packages that are only required for contributing or
testing, such as [`mypy`](https://www.mypy-lang.org/). Since v0.3.0 we strive
to have a codebase that can pass _at least_ `mypy --allow-redefinition`,
_at least_ on commits tagged with a version number.

At the moment the only optional package is
[`rich`](https://github.com/Textualize/rich).
When installed, it provides somewhat fancier output, especially on `--help`.

# Future work

* Support alternative simulation heuristics

* Support NuSMV

# Licensing caveats

`pyxmv` is MIT-licensed, but it is perfectly useless unless you obtain a copy
of nuXmv. Licensing restrictions forbid me from redistributing it, but it may
be downloaded [here](https://nuxmv.fbk.eu/download.html)
