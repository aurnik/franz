"""Guard: fail loudly if franz's name->index map has drifted from the live FX.

The bundle (`parameters.yaml`) addresses Pigments params by *index*, carrying the display
`name` only for humans + integrity. If the loaded plugin's param list ever shifts (different
Pigments version, a preset that reorders, a bad dump), an index in the bundle can point at a
different live param than its `name` claims — writes then land on the wrong control while
read-back from that same wrong index stays self-consistent (the exact Utility-bypass class of
bug). This check reads every live param name via TrackFX_GetParamName and asserts the bundle's
name==live name at each index.

Run with Reaper up (Pigments on the 'Franz' track):
    uv run franz-checkmap          # exits non-zero on any drift
"""

from __future__ import annotations

import sys
from pathlib import Path

from adapters.daws.reaper.reaper_adapter import ReaperAdapter, ReaperError
from franz_mcp.knowledge import Knowledge

BUNDLE_DIR = Path(__file__).resolve().parents[2] / "plugins" / "pigments"


def compare(adapter: ReaperAdapter, knowledge: Knowledge) -> list[tuple[str, int, str, str]]:
    """Return [(qualified, index, bundle_name, live_name)] for every drifted param."""
    live = {p["index"]: p["name"] for p in adapter.dump_params()}
    drift = []
    for p in knowledge.all_params():
        live_name = live.get(p.index)
        if live_name != p.name:
            drift.append((p.qualified, p.index, p.name, live_name or "<out of range>"))
    return drift


def main() -> None:
    knowledge = Knowledge(BUNDLE_DIR)
    adapter = ReaperAdapter()
    try:
        project = adapter.connect()
    except ReaperError as exc:
        print(f"FAIL: cannot verify param map — {exc}", file=sys.stderr)
        sys.exit(2)

    drift = compare(adapter, knowledge)
    total = len(knowledge.all_params())
    if not drift:
        print(f"OK: all {total} bundle params match the live Pigments param list "
              f"(project {project!r}).")
        return

    print(f"DRIFT: {len(drift)}/{total} bundle params no longer match the live FX "
          f"(project {project!r}):", file=sys.stderr)
    for qualified, index, bundle_name, live_name in drift:
        print(f"  {qualified} @ idx {index}: bundle={bundle_name!r} live={live_name!r}",
              file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
