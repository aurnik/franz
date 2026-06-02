# Plugin bundles

A plugin bundle is the synth-specific knowledge Franz needs to shape *that* instrument with
language. It's pure data and prose — no code. The portable MCP server (`franz_mcp/`, the
LLM-facing tool server) loads a bundle by path; the DAW adapter is what actually moves the
parameters.

A bundle has five files, each read by a different consumer:

| File | Read by | What it holds |
|---|---|---|
| `parameters.yaml` | the server | The hand-picked param map: groups → tool name → params → index/name/units/toggle polarity. Drives which `set_*` tools exist and what targets they accept. |
| `instructions.md` | the LLM (always-on) | The synth's operating guide: the base patch, what's fixed vs. movable, how to think about edits. Composed into the MCP `instructions` field. |
| `vocabulary.yaml` | the LLM (always-on) | Sonic-term → quality/cause/locate framework ("muddy", "boxy", "harsh"…). Appended to instructions. |
| `signal_flow.md` | the LLM (on-demand) | The stage map: how each stage shapes the sound, how changes propagate, what each move costs elsewhere. Served via the `get_signal_flow` tool. |
| `SETUP.md` | a human | How to build the init patch in the plugin's UI and why that's necessary. |

The split tracks real boundaries — combining any two would either force the model to read
human prose it doesn't need, or force a contributor to scroll past YAML to find setup
steps.

## Worked example: Pigments

`pigments/` is the reference bundle. Read `parameters.yaml` first to see the schema
(groups, tool names, param shape, `on_value` for inverted toggles), then `instructions.md`
to see how the bundle teaches the model to use those tools.

## Writing a new plugin bundle

1. **Get the full parameter list out of the plugin** via your DAW's scripting API. Write
   each one's index + display name to JSON; that's the raw material `parameters.yaml` is
   curated from.
2. **Hand-pick the sound-shaping params** — aim for 30–100 of the front-panel moves a
   sound designer reaches for, not every modulation-matrix cell.
3. **Group them into tools** (`set_oscillator`, `set_filter`, `set_fx`, …). Each group
   becomes one MCP tool with an enum of its targets, so groups should be small enough that
   their enum stays readable.
4. **Write `SETUP.md` for the init patch** — the engines, filter algorithms, FX slots,
   and waveforms that have to exist in the loaded patch for the param map to mean
   anything. Those are typically *not* automatable params; they're plugin UI state.
5. **Write `instructions.md` and `vocabulary.yaml`** to teach the model how to reason
   about this instrument.
6. **Write `signal_flow.md`** describing the stage map and the propagation costs of each
   move. This is the prose that lets the model reason about *where* in the chain to act,
   not just which knob to turn.

Contributions are welcome.
