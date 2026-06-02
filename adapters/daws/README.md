# DAW adapters

A DAW adapter is the glue between Franz's portable MCP server (`franz_mcp/` — the
LLM-facing tool server) and a specific host. The MCP server is DAW-agnostic — every
DAW-specific decision (how to address a plugin, how to read/write a parameter, how to
read what notes are being played) lives here.

The contract is `franz_mcp.adapter.DawAdapter` — a small abstract base class (ABC). A new
adapter implements it against whatever remote-control mechanism the host exposes — a
Python scripting API, OSC (Open Sound Control messages), a vendor SDK, or a controller
protocol — and ships a launcher that wires it into `franz_mcp.server.build_server`.

## Worked example: Reaper

`reaper/` is the reference implementation. Read it in this order:

1. **`reaper_adapter.py`** — the `DawAdapter` subclass. Talks to Reaper via reapy (a
   Python bridge that runs commands inside Reaper from an outside process), finds a track
   and the Pigments FX on it, and batches reads/writes through `reapy.inside_reaper()` so
   N parameters move in a single round-trip instead of N.
2. **`serve.py`** — the launcher (exposed as `franz-reaper`). ~20 lines that build the
   adapter, load a plugin bundle, call `build_server`, and run the MCP server over stdio
   (the standard local-process transport MCP clients use). The bundle path is what
   determines which synth the LLM is shaping — see `../plugins/README.md`.

## Writing a new DAW adapter

The adapter only has to satisfy the ABC. The Reaper adapter is one way; another DAW will
probably look different — its remote-control mechanism, how it addresses tracks/devices,
and what a "parameter" means are all host-specific. Those mechanics live entirely inside
your adapter and don't leak past the ABC methods.

Things worth knowing:

- **`read_state` / `apply` take *lists*, on purpose.** Franz reads or writes dozens of
  parameters per turn. If your host's control API is per-parameter, batch underneath —
  one MCP turn shouldn't be one round-trip per parameter.
- **Parameter IDs are opaque to `franz_mcp`.** They're whatever your adapter and the
  plugin bundle agree on. Reaper uses integer indices; a different host/plugin might use
  string idents, paths, or UUIDs.
- **`probe()` / `read_observation()` are where a spectral analyzer would plug in.** Leave
  them raising `NotImplementedError` if you're not wiring one up — Franz works without it.
- **No agent loop in the adapter.** The adapter exposes capabilities; the MCP server
  exposes tools; whatever MCP client the user has connected drives the conversation.

Contributions are welcome.
