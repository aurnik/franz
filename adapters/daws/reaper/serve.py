"""Reaper launcher for the Franz MCP server (the command an MCP client runs). Wires the
concrete ReaperAdapter + the Pigments bundle into the portable server.

    uv run franz-reaper           # stdio MCP server

Reaper must be running (launched via adapters/daws/reaper/launch_reaper.sh) with the
Franz track + Pigments. If it isn't up yet, the server still starts and connects on the
first tool call.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from adapters.daws.reaper.reaper_adapter import ReaperAdapter, ReaperError
from franz_mcp.server import build_server

BUNDLE_DIR = Path(__file__).resolve().parents[2] / "plugins" / "pigments"


def main() -> None:
    # FRANZ_ABLATE=1 serves the same tools/params with the documentation layer stripped
    # (no signal-flow doc, vocabulary, instructions, or rich descriptions) — the "no-doc"
    # side of the demo A/B. Register it as a separate MCP entry named 'franz-naive' so both
    # can run at once and you switch by conversation, no restart. See demo/runbook.md.
    ablate = os.environ.get("FRANZ_ABLATE", "").lower() in ("1", "true", "yes")
    name = "franz-naive" if ablate else "franz"
    adapter = ReaperAdapter()
    try:
        project = adapter.connect()
        print(f"{name}: connected to Reaper ({project!r}).", file=sys.stderr)
    except ReaperError as exc:
        print(
            f"{name}: Reaper not reachable yet ({exc}). Will connect on first "
            "tool call.",
            file=sys.stderr,
        )
    mcp = build_server(adapter, BUNDLE_DIR, name=name, ablate=ablate)
    mcp.run()  # stdio transport by default


if __name__ == "__main__":
    main()
