# Pigments — required patch setup

## Why an init patch is needed

Franz can only move what the host exposes as an automatable parameter. Reaper (like most
DAWs) surfaces a plugin's parameters via its automation API, and most synths — Pigments
included — only expose **continuous knobs** that way: cutoff, resonance, dry/wet, env times,
levels. Discrete UI choices (which engine type is loaded, which filter algorithm is
selected, which wavetable a slot points at, whether an effect slot holds a distortion or a
chorus) are *not* parameters at all. They're patch state set in the plugin's UI.

So the engines, filter algorithms, FX slots, and wavetable have to be **pre-configured in a
saved patch** before Franz can shape it — they're the fixed scaffolding inside which the
LLM moves knobs. If the live patch doesn't match what `parameters.yaml` was built against,
the params will still read and write, but they'll move the wrong things (or nothing
audible).

Save the patch below as a Pigments preset and load it on the track Franz is pointed at.

## Engines

- **Engine 1 tab:** **Wavetable** engine, **On** (not bypassed), loaded with the **basic
  waveforms** wavetable.
- **Engine 2 tab:** **Wavetable** engine, **On**, same **basic waveforms** wavetable.
- **Basic-waveforms Position map** (both engines): Position morphs **sine → triangle → saw →
  square** across 0→1, so `engine*_position` doubles as a waveform selector on this patch —
  `0.0` = sine, `~0.33` = triangle, `~0.67` = saw, `1.0` = square. (Waveform/wavetable
  *selection* is otherwise a UI choice, not a param — this mapping only holds while this
  wavetable is loaded.)
- **Utility engine:** **On**. Used as the sub/noise layer:
  - **Sub oscillator** enabled, a waveform chosen (Sine or Triangle for clean low weight),
    typically tuned −12 semitones.
  - **Noise 1** enabled with a noise/texture sample loaded (the `set_utility` noise controls
    shape level, filter, length, loop — but not which sample).
  - **Noise 2** optional (leave off if unused; `noise2_*` still address it if enabled).

> Why it matters: `set_oscillator` assumes Wavetable on both engines (it drives Position,
> Fold/Phase-Dist/Mod Amount, etc.). If an engine is Analog/Sample/Harmonic/Modal instead,
> those params do nothing. `set_utility` assumes the sub + noise sources exist.

## Filters

- **Filter 1: On.** Any algorithm (the bundle drives Cutoff/Resonance/Drive/Morph/Mode
  generically; `f1_mode` and `f1_morph` only bite on algorithms that have them).
- **Filter 2: Off** by default (the bundle can turn it on via `f2_on`).
- **Filter routing** set as desired (`filter_routing` selects the Sum/Split topology; the
  serial↔parallel blend is a separate knob).

## FX — Bus A inserts (order matters)

Bus A must hold these three effects in these slots, because the bundle addresses them by
slot, not by effect identity:

| Slot | Effect      | Bundle group / tool |
|------|-------------|---------------------|
| A1   | **Param EQ**    | `eq` / `set_eq`           |
| A2   | **Distortion**  | `distortion` / `set_distortion` |
| A3   | **Reverb**      | `reverb` / `set_reverb`   |

Order is deliberate: surgical EQ **before** distortion (clean the region before it is
driven), reverb **last**. Each effect is engaged at runtime via its Dry/Wet — they can sit
loaded-but-dry until Franz brings them in. Bus B and the Aux send are unused by the current
bundle.

## Always-on

- **Amp envelope** (`amp_env` / `set_envelope`) is hardwired to the VCA — always present,
  no setup needed.
- **Unison** (`set_unison`) addresses each Wavetable engine's unison section; off until engaged.

## Quick checklist

- [ ] Engine 1 = Wavetable, on
- [ ] Engine 2 = Wavetable, on
- [ ] Utility on: sub osc + Noise 1 loaded
- [ ] Filter 1 on, Filter 2 off
- [ ] Bus A: A1 Param EQ → A2 Distortion → A3 Reverb (loaded; Dry/Wet at taste)
- [ ] Saved as a preset and loaded on the target Reaper track
