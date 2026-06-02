"""FastMCP server — registers tools against an injected adapter + knowledge bundle.

Stays DAW-agnostic: it never imports a concrete adapter. A DAW-specific launcher
constructs the adapter and calls `build_server` (see adapters/daws/reaper/serve.py).
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from franz_mcp.adapter import DawAdapter
from franz_mcp.knowledge import Knowledge
from franz_mcp.tools import register_tools


def build_server(
    adapter: DawAdapter, bundle_dir: Path, name: str = "franz", ablate: bool = False
) -> FastMCP:
    knowledge = Knowledge(bundle_dir, ablate=ablate)
    mcp = FastMCP(name, instructions=knowledge.instructions or None)
    register_tools(mcp, adapter, knowledge)
    return mcp
