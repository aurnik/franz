# DAW adapters

A DAW adapter is the glue between Franz's portable MCP server (`franz_mcp/`) and a specific
host: Reaper, Ableton, Bitwig, Logic, etc. The MCP server is DAW-agnostic — every
DAW-specific decision (how to address a plugin, how to read/write a parameter, how to read
what notes are being played) lives here.

The contract is `franz_mcp.adapter.DawAdapter` — a small abstract base class. A new adapter
implements it against the host's native control surface (a scripting API, OSC, an SDK,
a remote-control protocol) and ships a launcher that wires it into
`franz_mcp.server.build_server`.

## Worked example: Reaper

`reaper/` is the reference implementation. Read it in this order:

1. **`reaper_adapter.py`** — the `DawAdapter` subclass. Talks to Reaper via reapy's
   distant API, locates a track + the Pigments FX on it, and batches reads/writes through
   `reapy.inside_reaper()` so N parameters move in one round-trip.
2. **`serve.py`** — the launcher. ~20 lines that build the adapter, load a plugin bundle,
   call `build_server`, and run the MCP server over stdio. The bundle path is what
   determines which synth the LLM is shaping — see `../plugins/README.md`.
3. **`dump_params.py`**, **`check_param_map.py`** — utilities for authoring and
   maintaining a plugin bundle against the live FX. Reaper-specific but the pattern
   transfers.

## Writing a new DAW adapter

The adapter only has to satisfy the ABC. The Reaper adapter is one way; another DAW will
probably look different — Ableton won't need a named track, Bitwig has its controller API,
Logic has Scripter. Those mechanics live entirely inside your adapter and don't leak past
the ABC methods.

Things worth knowing:

- **`read_state` / `apply` take *lists*, on purpose.** Franz reads or writes dozens of
  parameters per turn. If your host's control API is per-parameter, batch underneath —
  one MCP turn shouldn't be one round-trip per parameter.
- **Parameter IDs are opaque to `franz_mcp`.** They're whatever your adapter and the
  plugin bundle agree on. Reaper uses integer indices; a different host/plugin might use
  string idents, paths, or UUIDs.
- **`probe()` / `read_observation()` are the analyzer seam.** Leave them raising
  `NotImplementedError` if you're not implementing the analyzer — Franz works without it.
- **No agent loop in the adapter.** The adapter exposes capabilities; the MCP server
  exposes tools; a client (Claude Desktop, etc.) drives the conversation.

Contributions are welcome.
