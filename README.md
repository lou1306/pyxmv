# `pyxmv` - (Unofficial) Python interface to nuXmv

[nuXmv](https://nuxmv.fbk.eu/) is a state-of-the-art symbolic model checker for
the analysis of finite- and infinite- state systems

`pyxmv` is a (very much WIP) wrapper for the nuXmv command-line interface; it
aims at providing APIs for several features of the solver 

# Future work

* Parse states (from counterexamples or simulation traces) into structured data
  for easier interop

* Support verification

* Support alternative simulation heuristics

# Licensing caveats

`pyxmv` is MIT-licensed, but it is perfectly useless unless you obtain a copy
of nuXmv. Licensing restrictions forbid me from redistributing it, but it may
be downloaded [here](https://nuxmv.fbk.eu/download.html)