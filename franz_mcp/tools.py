"""Registers the model-facing and host-facing tools on a FastMCP server.

Model-facing (the LLM drives these):
  set_<group>(target, value)   one per bundle group, each with an enum of its targets
  get_parameter(parameter)     read one param back (normalized + formatted)

Checkpoint primitives (a host client or MCP Inspector drives these, not the model):
  get_state()                  batched read of every exposed param
  apply_state(state)           batched restore

Data-driven from the Knowledge bundle and talks only to the DawAdapter, so this module
stays DAW-agnostic. Values are normalized 0..1.
"""

import typing
from typing import TYPE_CHECKING

# NOTE: no `from __future__ import annotations` here. FastMCP introspects tool
# signatures with eval_str=True; the per-group `target: TargetEnum` annotation is a
# closure-local Literal that must stay a real object, not a deferred string.
#
# `target` is a typing.Literal, NOT an enum.Enum, on purpose: pydantic emits an Enum
# into `$defs` and references it from the property (`target: {"$ref": ...}`), but inlines
# a Literal directly as `{"type": "string", "enum": [...]}`. Clients that don't resolve
# `$ref`/`$defs` (Claude Desktop flattens without dereferencing) then see `target` as
# untyped — the model reads it as "anything goes" and passes null. Inlining keeps the
# allowed-targets list on the property so it survives every client.

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from franz_mcp.adapter import DawAdapter
    from franz_mcp.knowledge import Knowledge


def _check_normalized(value: float) -> float:
    if not isinstance(value, (int, float)) or not (0.0 <= value <= 1.0):
        raise ValueError(f"value must be normalized in [0.0, 1.0], got {value!r}")
    return float(value)


def _make_setter(adapter, knowledge, group):
    """Build one set_<group> tool whose `target` is an enum of that group's qualified
    parameter ids (e.g. 'oscillator.engine1_position') — the SAME ids get_parameter and
    get_state report and that this tool echoes back on success. One id everywhere, so a
    name the model just read can be passed straight into a set call without translation."""
    params = [knowledge.resolve(group, ln) for ln in knowledge.groups[group].labels]
    # The Literal's members are the qualified ids — exactly what the model passes and what
    # validation checks, inlined onto the property (see module note).
    TargetLiteral = typing.Literal[tuple(p.qualified for p in params)]

    def setter(target: TargetLiteral, value: float) -> str:
        value = _check_normalized(value)
        param = knowledge.resolve_qualified(target)
        raw = param.resolve_value(value)
        adapter.apply([(param.index, raw)])
        if param.is_toggle:
            # Show the semantic state, not the raw plugin label — for an inverted toggle
            # the plugin string ("Off" for a Bypass that means ON) reads backwards.
            shown = "on" if abs(raw - param.on_value) < 0.5 else "off"
        else:
            shown = adapter.read_formatted([param.index]).get(param.index, "").strip()
        suffix = f"  [{shown}]" if shown else ""
        return f"set {param.qualified} ({param.name}) = {value:.4f}{suffix}"

    setter.__name__ = knowledge.groups[group].tool
    toggles = [p.qualified for p in params if p.is_toggle]
    targets = ", ".join(p.qualified for p in params)
    toggle_note = (
        f" On/off targets ({', '.join(toggles)}) take value 1=on/audible, 0=off — "
        "franz maps that to the param's real polarity, so never guess; just use 1 or 0."
        if toggles else ""
    )
    setter.__doc__ = (
        f"{knowledge.groups[group].description} "
        f"value is normalized 0..1.{toggle_note} targets: {targets}."
    )
    return setter


def register_tools(mcp: "FastMCP", adapter: "DawAdapter", knowledge: "Knowledge") -> None:
    for group in knowledge.groups:
        tool = knowledge.groups[group].tool
        mcp.add_tool(_make_setter(adapter, knowledge, group), name=tool)

    ParamLiteral = typing.Literal[tuple(knowledge.qualified_labels())]

    def get_parameter(parameter: ParamLiteral) -> dict:
        """Read one exposed parameter: its normalized value and formatted display value.
        For on/off toggles, also returns `on` (true = currently ON/audible/engaged),
        resolved against the param's real polarity so it's unambiguous regardless of the
        display name or which normalized extreme means 'on'."""
        param = knowledge.resolve_qualified(parameter)
        norm = float(adapter.read_state([param.index])[param.index])
        result = {
            "parameter": param.qualified,
            "name": param.name,
            "normalized": round(norm, 6),
        }
        if param.is_toggle:
            on = abs(norm - param.on_value) < 0.5
            # `formatted` mirrors `on` so it can't read backwards; the raw plugin label
            # for an inverted toggle ("Off"/"Bypassed" at the ON extreme) would mislead.
            result["formatted"] = "on" if on else "off"
            result["on"] = on
        else:
            result["formatted"] = adapter.read_formatted([param.index]).get(param.index, "").strip()
        return result

    mcp.add_tool(get_parameter, name="get_parameter")

    def get_played_notes() -> dict:
        """The register the synth is being played across — read live from the track's MIDI item
        as note names + frequencies (not an audio analysis). Returns the distinct `pitches`
        low->high plus the `lowest` / `highest` bounds. Use it to anchor frequency reasoning: a
        term like 'boxy' or 'air' sits at a place that depends on the register, so read this to
        know the fundamentals you're reasoning relative to before deciding where a quality lives."""
        return adapter.read_played_notes()

    mcp.add_tool(get_played_notes, name="get_played_notes")

    # -- always-on bundle knowledge, served as a tool ------------------------
    # The same intro + vocabulary that compose the MCP `instructions` field, also
    # exposed as a tool: not every client injects a server's instructions field (e.g.
    # Claude Desktop drops it), so the load-bearing knowledge must travel a channel
    # every client surfaces — tool definitions. Clients that DO honor instructions get
    # it both ways at trivial cost.
    if knowledge.instructions:
        synth_guide_text = knowledge.instructions

        def get_synth_guide() -> str:
            return synth_guide_text

        mcp.add_tool(
            get_synth_guide,
            name="get_synth_guide",
            description=(
                "The synth's operating guide: the base patch you're shaping (engines, "
                "filters, FX rack, what's fixed vs. movable) and the perceptual "
                "vocabulary that maps a listener's words ('boxy', 'muddy', 'harsh', "
                "'airy', 'weight') to the spectral region they name and the tradeoffs of "
                "acting there. Call this FIRST, before translating any sonic description "
                "into parameter moves — it is the dictionary that turns vague language "
                "into a targeted, defensible change. Not needed when the user names a "
                "specific parameter to set."
            ),
        )

    # -- on-demand signal-flow knowledge -------------------------------------
    # Served as a tool (not always-on context) so the model pulls it only when a
    # request hinges on signal-path reasoning, and the call is visible in the trace.
    if knowledge.signal_flow:
        signal_flow_text = knowledge.signal_flow

        def get_signal_flow() -> str:
            return signal_flow_text

        mcp.add_tool(
            get_signal_flow,
            name="get_signal_flow",
            description=(
                "The synth's signal-flow map: how each stage (engines, filters, FX rack, "
                "amp) shapes the sound, how a change at one stage propagates downstream, "
                "and the tradeoffs of each move. Consult this whenever a request requires "
                "deciding WHERE in the signal path to act or WHAT a change costs elsewhere "
                "— removing mud without losing weight, recovering brightness, choosing EQ "
                "vs filter vs distortion, series vs parallel filtering. Not needed for a "
                "single parameter the user names explicitly."
            ),
        )

    # -- checkpoint primitives -----------------------------------------------

    def get_state() -> dict[str, dict]:
        """Read every exposed param in one round-trip. Each entry carries `normalized`
        (0..1, the checkpoint value apply_state takes back) plus `formatted`
        (the synth's own display value, e.g. '18.0', '-10.5 dB') and, for on/off toggles,
        `on` (true = currently ON/audible) with `formatted` set to 'on'/'off' to match it.
        Trust `on` and `formatted`, never the raw magnitude: a param named `*.enabled` can
        read normalized 1.0 while being OFF, because Pigments' toggle polarity is inconsistent.
        NOTE: `formatted` for time params (envelope/delay/reverb times) is unit-less and the
        unit differs per param — don't read an absolute time off it (see get_synth_guide)."""
        params = knowledge.all_params()
        norm = adapter.read_state([p.index for p in params])
        fmt = adapter.read_formatted([p.index for p in params])
        state = {}
        for p in params:
            n = float(norm[p.index])
            if p.is_toggle:
                on = abs(n - p.on_value) < 0.5
                # `formatted` mirrors `on` so an inverted toggle can't read backwards.
                entry = {"normalized": round(n, 6), "formatted": "on" if on else "off", "on": on}
            else:
                entry = {"normalized": round(n, 6), "formatted": fmt.get(p.index, "").strip()}
            state[p.qualified] = entry
        return state

    def apply_state(state: dict) -> str:
        """Checkpoint restore: write a {parameter: value} map in one round-trip. Each
        value is either a bare normalized float or a get_state entry (a dict with a
        `normalized` key) — so a get_state result can be handed straight back."""
        changes = []
        for qualified, value in state.items():
            param = knowledge.resolve_qualified(qualified)
            norm = value["normalized"] if isinstance(value, dict) else value
            changes.append((param.index, _check_normalized(norm)))
        adapter.apply(changes)
        return f"applied {len(changes)} parameters"

    mcp.add_tool(get_state, name="get_state")
    mcp.add_tool(apply_state, name="apply_state")
