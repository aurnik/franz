"""The DAW seam.

`franz_mcp` knows nothing about Reaper, reapy, gmem, or JSFX. It depends only on
this interface and a synth knowledge bundle. Everything DAW-specific lives behind a
concrete adapter (see `adapters/daws/reaper/` for the reference implementation).

The interface exposes four capabilities:

    read_state(param_ids) -> dict    batched read
    apply(changes) -> None           batched write
    probe()                          fire the analysis excitation (optional)
    read_observation() -> dict       interpreted spectral features (optional)

`probe`/`read_observation` are the analyzer seam. A concrete adapter may leave them
raising NotImplementedError; Franz works without an analyzer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

# An opaque parameter id whose meaning is defined by the concrete adapter + the synth
# bundle — franz_mcp never interprets it. For Reaper/Pigments it's the param index;
# a name string is also accepted where unambiguous.
ParamId = int | str
# Normalized value in [0.0, 1.0], matching TrackFX_*ParamNormalized.
Normalized = float


class DawAdapter(ABC):
    """The contract every DAW backend implements."""

    @abstractmethod
    def read_state(self, param_ids: list[ParamId]) -> dict[ParamId, Normalized]:
        """Return the normalized value of each requested parameter, in one round-trip."""

    @abstractmethod
    def apply(self, changes: list[tuple[ParamId, Normalized]]) -> None:
        """Write each (param, normalized) pair, in one round-trip."""

    def read_formatted(self, param_ids: list[ParamId]) -> dict[ParamId, str]:
        """Human-readable display values per param (e.g. '440 Hz'). Optional — adapters
        that can't format return empty strings."""
        return {pid: "" for pid in param_ids}

    def read_played_notes(self) -> dict:
        """The register the synth is being played across, from the track's MIDI item — distinct
        note *numbers* (not audio), low->high, with the range bounds: {pitches, lowest, highest}.
        Gives the LLM the fundamentals to anchor frequency reasoning (where 'boxy'/'air' sits
        depends on register). No spectral analysis. Optional; adapters that can't read it return
        an empty structure."""
        return {"pitches": [], "lowest": None, "highest": None}

    def probe(self) -> None:
        """Fire the analysis excitation (a fixed probe note). Optional."""
        raise NotImplementedError("this adapter does not implement the analyzer")

    def read_observation(self) -> dict:
        """Return the interpreted spectral feature set. Optional."""
        raise NotImplementedError("this adapter does not implement the analyzer")
