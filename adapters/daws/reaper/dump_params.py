"""Capture the full Pigments parameter dump to JSON.

The machine-extracted reference (`adapters/plugins/pigments/param_dump.json`): every
param's index, display name, and ident. The hand-picked `parameters.yaml` is curated
from it.

    uv run franz-dump                         # -> adapters/plugins/pigments/param_dump.json
    uv run franz-dump --out /tmp/dump.json    # custom path
    uv run franz-dump --track Franz
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from adapters.daws.reaper.reaper_adapter import ReaperAdapter, ReaperError

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "plugins" / "pigments" / "param_dump.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dump all Pigments params to JSON.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output JSON path.")
    parser.add_argument("--track", default="Franz", help="Track name (default: Franz).")
    args = parser.parse_args(argv)

    adapter = ReaperAdapter(track_name=args.track)
    try:
        project = adapter.connect()
        print(f"Connected ({project!r}); dumping {adapter.fx_name_contains!r} params...")
        params = adapter.dump_params()
    except ReaperError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "synth": "Pigments",
        "fx_name_match": adapter.fx_name_contains,
        "n_params": len(params),
        "params": params,
    }
    args.out.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {len(params)} params -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
