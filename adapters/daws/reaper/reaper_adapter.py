"""Reaper backend for the DAW seam, via reapy's distant API.

Locates the Pigments FX on a named track and reads/writes normalized values in batched
round-trips through `reapy.inside_reaper()`. Params are addressed by index — Pigments
exposes no real idents (TrackFX_GetParamIdent returns the index as a string).

About `with reapy.inside_reaper():` — every reapy call is normally a separate network
round-trip to Reaper's distant-API server (slow). Inside the `with` block, all the
ReaScript calls are bundled and sent as a single round-trip. We use it anywhere we make
more than one call (dumping every param, reading/writing a batch).

probe()/read_observation() (the analyzer path) are not implemented; only
read_state/apply, which is what the model-facing tools and checkpoint primitives need.
"""

from __future__ import annotations

import reapy

from franz_mcp.adapter import DawAdapter, Normalized, ParamId


class ReaperError(RuntimeError):
    """Raised when the Reaper project isn't in the expected shape."""


class ReaperAdapter(DawAdapter):
    def __init__(
        self,
        track_name: str = "Franz",
        fx_name_contains: str = "Pigments",
    ) -> None:
        self.track_name = track_name
        self.fx_name_contains = fx_name_contains.lower()
        self._track_id: str | None = None
        self._fx_index: int | None = None
        self._project_name: str = ""
        self._name_to_index: dict[str, int] = {}
        self._params: list[dict] = []

    # -- connection / location ------------------------------------------------

    def connect(self) -> str:
        """Connect to Reaper and locate the track + Pigments FX. Returns project name.

        Idempotent: returns the cached project name if already located. Raises
        ReaperError with an actionable message if the distant API is off or the
        expected track/FX is missing.
        """
        if self._located:
            return self._project_name
        try:
            reapy.connect()
            with reapy.inside_reaper():
                project = reapy.Project()
                project_name = project.name
                track = self._find_track(project)
                fx = self._find_fx(track)
                self._track_id = track.id
                self._fx_index = fx.index
                self._project_name = project_name
            return project_name
        except ReaperError:
            raise  # already actionable (missing track / FX)
        except Exception as exc:
            # reapy.connect() doesn't raise when the server is unreachable; the failure
            # surfaces here (no selected client -> AttributeError, or socket errors).
            raise ReaperError(
                "Could not reach Reaper's distant API (reapy server on port 2306 isn't "
                "responding). Checklist: (1) Reaper is running, launched via "
                "adapters/daws/reaper/launch_reaper.sh so PYTHONHOME is set; (2) start the server by "
                "running the Reaper action 'Custom: activate_reapy_server.py'; "
                "(3) verify with: lsof -nP -iTCP:2306 -sTCP:LISTEN. If this MCP server "
                "launched before Reaper was ready, just retry — the next call reconnects."
            ) from exc

    def _find_track(self, project) -> "reapy.Track":
        for track in project.tracks:
            if track.name == self.track_name:
                return track
        names = [t.name for t in project.tracks]
        raise ReaperError(
            f"No track named {self.track_name!r}. Found tracks: {names}. "
            "Create a track named 'Franz' and load Pigments on it."
        )

    def _find_fx(self, track) -> "reapy.FX":
        for fx in track.fxs:
            if self.fx_name_contains in fx.name.lower():
                return fx
        names = [fx.name for fx in track.fxs]
        raise ReaperError(
            f"No FX matching {self.fx_name_contains!r} on track {self.track_name!r}. "
            f"Found FX: {names}."
        )

    @property
    def _located(self) -> bool:
        return self._track_id is not None and self._fx_index is not None

    def _ensure_connected(self) -> None:
        """Connect+locate on first use, so the MCP server works even if it launched
        before Reaper was ready (the first tool call establishes the connection)."""
        if not self._located:
            self.connect()

    # -- parameter dump / resolution -----------------------------------------

    def dump_params(self) -> list[dict]:
        """Return [{index, name, ident}] for every Pigments parameter, in one hop.

        Note: for Pigments, ident == str(index) (no semantic idents), so the bundle keys
        off index. The ident field is kept for plugins that do expose real ones.
        """
        self._ensure_connected()
        rpr = reapy.reascript_api
        with reapy.inside_reaper():
            fx = reapy.FX(parent_id=self._track_id, index=self._fx_index)
            n = fx.n_params
            params = []
            for i in range(n):
                # ReaScript's GetParam* functions fill an out-string buffer; reapy returns
                # it as a tuple where index 4 holds the filled string. `""` and `1024` are
                # the buffer + capacity that ReaScript needs as inputs.
                name = rpr.TrackFX_GetParamName(
                    self._track_id, self._fx_index, i, "", 1024
                )[4]
                ident = rpr.TrackFX_GetParamIdent(
                    self._track_id, self._fx_index, i, "", 1024
                )[4]
                params.append({"index": i, "name": name, "ident": ident})
        self._params = params
        self._name_to_index = {p["name"]: p["index"] for p in params}
        return params

    def find_params(self, *substrings: str) -> list[dict]:
        """Return dumped params whose name contains any of the given substrings (ci)."""
        if not self._params:
            self.dump_params()
        needles = [s.lower() for s in substrings]
        return [
            p
            for p in self._params
            if any(s in p["name"].lower() for s in needles)
        ]

    def _ensure_dumped(self) -> None:
        """Populate the param map. Runs its own round-trip, so call it *before*
        opening a read_state/apply `inside_reaper()` block (reapy doesn't nest them)."""
        if not self._params:
            self.dump_params()

    def _resolve(self, param_id: ParamId) -> int:
        """Map a param id to its index. Accepts an int index, a numeric string, or a
        unique display name. Pure lookup; assumes the dump already ran (_ensure_dumped).

        Pigments idents == index, so names are the only human-readable handle — but 55
        names are ambiguous (e.g. two 'Coarse'), so the bundle addresses by index.
        """
        if isinstance(param_id, int) or (
            isinstance(param_id, str) and param_id.lstrip("-").isdigit()
        ):
            idx = int(param_id)
            if not (0 <= idx < len(self._params)):
                raise ReaperError(f"Param index out of range: {idx}")
            return idx
        matches = [p["index"] for p in self._params if p["name"] == param_id]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ReaperError(f"Unknown parameter: {param_id!r}")
        raise ReaperError(
            f"Ambiguous parameter name {param_id!r} ({len(matches)} matches); "
            f"address it by index instead."
        )

    # -- DawAdapter: state read / write --------------------------------------

    def read_state(
        self, param_ids: list[ParamId]
    ) -> dict[ParamId, Normalized]:
        self._ensure_connected()
        self._ensure_dumped()
        rpr = reapy.reascript_api
        with reapy.inside_reaper():
            indices = {pid: self._resolve(pid) for pid in param_ids}
            return {
                pid: rpr.TrackFX_GetParamNormalized(
                    self._track_id, self._fx_index, idx
                )
                for pid, idx in indices.items()
            }

    def apply(self, changes: list[tuple[ParamId, Normalized]]) -> None:
        self._ensure_connected()
        self._ensure_dumped()
        rpr = reapy.reascript_api
        with reapy.inside_reaper():
            resolved = [(self._resolve(pid), value) for pid, value in changes]
            for idx, value in resolved:
                rpr.TrackFX_SetParamNormalized(
                    self._track_id, self._fx_index, idx, float(value)
                )

    def read_formatted(self, param_ids: list[ParamId]) -> dict[ParamId, str]:
        """Return each param's human-readable display value (e.g. '440 Hz', '-6.0 dB').

        Only works for FX exposing Cockos VST extensions; Pigments does.
        """
        self._ensure_connected()
        self._ensure_dumped()
        rpr = reapy.reascript_api
        with reapy.inside_reaper():
            indices = {pid: self._resolve(pid) for pid in param_ids}
            return {
                pid: rpr.TrackFX_GetFormattedParamValue(
                    self._track_id, self._fx_index, idx, "", 256
                )[4]
                for pid, idx in indices.items()
            }

    _NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    @classmethod
    def _note_info(cls, midi: int) -> dict:
        return {
            "midi": midi,
            "note": f"{cls._NOTE_NAMES[midi % 12]}{midi // 12 - 1}",
            "hz": round(440.0 * 2 ** ((midi - 69) / 12), 1),
        }

    def read_played_notes(self) -> dict:
        """The register the synth is being played across, from the track's MIDI item(s) — the
        distinct note numbers (not an audio analysis), low->high, with the range bounds:

            pitches:          [{midi, note, hz}] low->high.
            lowest / highest: the range bounds (the fundamentals to reason relative to).

        Gives the LLM the register to anchor frequency reasoning (where 'boxy'/'air' sits
        depends on register). Note timing is deliberately omitted: Franz's controls are
        patch-global, so a time-localized complaint isn't actionable — the range is the signal.
        MIDI_GetNote returns the pitch at tuple index 8.
        """
        self._ensure_connected()
        rpr = reapy.reascript_api
        pitches: set[int] = set()
        with reapy.inside_reaper():
            for i in range(rpr.GetTrackNumMediaItems(self._track_id)):
                item = rpr.GetTrackMediaItem(self._track_id, i)
                take = rpr.GetActiveTake(item)
                if not take or not rpr.TakeIsMIDI(take):
                    continue
                note_cnt = rpr.MIDI_CountEvts(take, 0, 0, 0)[2]
                for j in range(note_cnt):
                    pitches.add(rpr.MIDI_GetNote(take, j, 0, 0, 0, 0, 0, 0, 0)[8])
        ordered = [self._note_info(p) for p in sorted(pitches)]
        return {
            "pitches": ordered,
            "lowest": ordered[0] if ordered else None,
            "highest": ordered[-1] if ordered else None,
        }
