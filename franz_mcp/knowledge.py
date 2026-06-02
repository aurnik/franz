"""Loads a synth knowledge bundle.

A bundle is pure data under `adapters/plugins/<plugin>/`. `parameters.yaml` is the
hand-picked param schema; `instructions.md` + `vocabulary.yaml` compose the server's
always-on instructions field; `signal_flow.md` is served on demand via the
`get_signal_flow` tool. DAW-agnostic — knows param labels, indices, and prose, but
nothing about how a DAW reads or writes them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Param:
    group: str
    label: str
    name: str  # Pigments display name, for humans + integrity checks
    index: int  # the addressable id handed to the adapter
    sample: str  # formatted value at capture time — a unit hint, not a default
    on_value: float | None = None  # for on/off toggles: the normalized value meaning
    # ON/engaged/audible. Pigments' toggle polarity is inconsistent (some on=0.0, some
    # on=1.0), so set_* takes a uniform semantic (1=on, 0=off) and maps it through this.

    @property
    def qualified(self) -> str:
        """Globally-unique id, e.g. 'filter.f1_cutoff' (labels repeat across groups)."""
        return f"{self.group}.{self.label}"

    @property
    def is_toggle(self) -> bool:
        return self.on_value is not None

    def resolve_value(self, value: float) -> float:
        """Map a tool-facing value to the raw normalized to write. Continuous params pass
        through unchanged. Toggles use a uniform semantic — value>=0.5 means ON, else OFF —
        so the model never has to know a given param's internal polarity."""
        if self.on_value is None:
            return value
        # `on_value` is the normalized value that means ON for this toggle (0.0 or 1.0).
        # Its complement (1.0 - on_value) is therefore OFF.
        return self.on_value if value >= 0.5 else 1.0 - self.on_value


@dataclass(frozen=True)
class Group:
    name: str
    tool: str
    description: str
    labels: tuple[str, ...]


class Knowledge:
    def __init__(self, bundle_dir: Path, ablate: bool = False):
        """`ablate=True` strips the documentation layer for the demo A/B: no signal-flow
        doc, no vocabulary, no instructions, and bare group descriptions. The mechanical
        surface (same tools, params, units, polarity) is untouched — so the only variable
        is the prose IP. Lets you show the same model with and without the documentation."""
        self.bundle_dir = Path(bundle_dir)
        self.ablate = ablate
        data = yaml.safe_load((self.bundle_dir / "parameters.yaml").read_text())
        self.synth: str = data["synth"]
        self.groups: dict[str, Group] = {}
        self._by_qualified: dict[str, Param] = {}
        self._by_group_label: dict[tuple[str, str], Param] = {}

        # Bundle prose. signal_flow is served on demand via a tool; instructions.md +
        # vocabulary compose the always-on instructions field. All optional per bundle.
        # Under ablation, all prose is withheld (so get_synth_guide / get_signal_flow
        # never register and the instructions field is empty).
        self.signal_flow: str = "" if ablate else self._read_optional("signal_flow.md")
        self.vocabulary: str = "" if ablate else self._read_optional("vocabulary.yaml")
        self.instructions: str = "" if ablate else self._compose_instructions()

        for group_name, ginfo in data["groups"].items():
            labels = tuple(ginfo["params"].keys())
            description = (
                f"Set a {group_name} parameter." if ablate else ginfo["description"]
            )
            self.groups[group_name] = Group(
                name=group_name,
                tool=ginfo["tool"],
                description=description,
                labels=labels,
            )
            for label, pinfo in ginfo["params"].items():
                on_value = pinfo.get("on_value")
                p = Param(
                    group=group_name,
                    label=label,
                    name=pinfo["name"],
                    index=int(pinfo["index"]),
                    sample=str(pinfo.get("sample", "")),
                    on_value=None if on_value is None else float(on_value),
                )
                self._by_qualified[p.qualified] = p
                self._by_group_label[(group_name, label)] = p

    def _read_optional(self, filename: str) -> str:
        path = self.bundle_dir / filename
        return path.read_text().strip() if path.exists() else ""

    def _compose_instructions(self) -> str:
        """Always-on instructions field: bundle framing + vocabulary. The heavier
        signal-flow map is left out here and pulled on demand via get_signal_flow."""
        parts = []
        intro = self._read_optional("instructions.md")
        if intro:
            parts.append(intro)
        if self.vocabulary:
            parts.append(f"```yaml\n{self.vocabulary}\n```")
        return "\n\n".join(parts)

    def resolve(self, group: str, label: str) -> Param:
        try:
            return self._by_group_label[(group, label)]
        except KeyError:
            raise KeyError(f"No param {label!r} in group {group!r}")

    def resolve_qualified(self, qualified: str) -> Param:
        try:
            return self._by_qualified[qualified]
        except KeyError:
            raise KeyError(f"Unknown parameter {qualified!r}")

    def all_params(self) -> list[Param]:
        return list(self._by_qualified.values())

    def qualified_labels(self) -> list[str]:
        return list(self._by_qualified.keys())
