"""Compone y sintetiza música original para cada vídeo.

Uso: .venv/bin/python -m tools.music --mood cheerful --seconds 20 [--bpm 118] [--seed 7]
     --out music.wav   (escribe también music.json con bpm, beats y compases)

Misma semilla = misma canción. El tempo es exacto, así que los cortes pueden caer en el beat.
"""
import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import synth
from .audio import place, write_wav

SCALES = {"major": (0, 2, 4, 5, 7, 9, 11), "minor": (0, 2, 3, 5, 7, 8, 10)}
KEY_ROOTS = {"C": 60, "D": 62, "F": 65, "G": 67, "A": 57}

# Posiciones en semicorcheas (0–15) dentro de un compás de 4/4.
DRUM_PATTERNS = {
    "pop": {"kick": (0, 8), "clap": (4, 12), "hat": (0, 2, 4, 6, 8, 10, 12, 14),
            "shaker": (1, 3, 5, 7, 9, 11, 13, 15)},
    "bouncy": {"kick": (0, 4, 8, 12), "clap": (4, 12), "hat": (2, 6, 10, 14)},
    "tiptoe": {"kick": (0, 10), "hat": (0, 4, 8, 12)},
    "big": {"kick": (0, 3, 8, 11), "clap": (4, 12), "hat": (0, 2, 4, 6, 8, 10, 12, 14)},
}
DRUM_GAINS = {"kick": 0.55, "clap": 0.28, "hat": 0.12, "shaker": 0.08}

# Ritmos de melodía: (inicio, duración) en semicorcheas.
RHYTHMS = (
    ((0, 2), (2, 2), (4, 4), (8, 2), (10, 2), (12, 4)),
    ((0, 4), (4, 2), (6, 2), (8, 6), (14, 2)),
    ((0, 2), (2, 2), (4, 2), (6, 2), (8, 8)),
    ((0, 6), (6, 2), (8, 4), (12, 4)),
    ((2, 2), (4, 2), (6, 2), (8, 4), (12, 2), (14, 2)),
)


@dataclass(frozen=True)
class Mood:
    scale: str
    bpm_range: tuple[int, int]
    lead: str
    chords: str  # "strum" | "oompah" | "arp"
    chord_instrument: str
    drums: str | None
    progressions: tuple[tuple[int, ...], ...]
    keys: tuple[str, ...]


MOODS = {
    "cheerful": Mood("major", (112, 124), "marimba", "strum", "pluck", "pop",
                     ((0, 4, 5, 3), (0, 5, 3, 4), (3, 0, 4, 5)), ("C", "D", "F", "G")),
    "silly": Mood("major", (128, 140), "pluck", "oompah", "pluck", "bouncy",
                  ((0, 4, 0, 4), (0, 3, 4, 0)), ("C", "F", "G")),
    "sneaky": Mood("minor", (96, 108), "pizz", "arp", "pizz", "tiptoe",
                   ((0, 5, 3, 4), (0, 3, 4, 0)), ("A", "D")),
    "sleepy": Mood("major", (68, 80), "bell", "arp", "pluck", None,
                   ((0, 5, 3, 4), (3, 4, 0, 0)), ("C", "F")),
    "epic": Mood("major", (120, 132), "bell", "strum", "pluck", "big",
                 ((5, 3, 0, 4), (0, 4, 5, 3)), ("D", "G")),
}


def resolve_bpm(mood: str, bpm: float | None, seed: int) -> float:
    if bpm:
        return float(bpm)
    lo, hi = MOODS[mood].bpm_range
    return float(np.random.default_rng(seed).integers(lo, hi + 1))


def _degree_midi(root: int, scale: tuple[int, ...], degree: int) -> int:
    octave, idx = divmod(degree, 7)
    return root + 12 * octave + scale[idx]


def _melody_bar(rng, rhythm, chord_root: int, start_degree: int, cadence: bool):
    """Devuelve [(inicio16, dur16, grado)] y el último grado usado."""
    chord_tones = {chord_root % 7, (chord_root + 2) % 7, (chord_root + 4) % 7}
    notes, degree = [], start_degree
    for i, (onset, length) in enumerate(rhythm):
        if onset in (0, 8):  # tiempos fuertes: nota del acorde más cercana
            candidates = [d for d in range(degree - 3, degree + 4) if d % 7 in chord_tones]
            degree = min(candidates, key=lambda d: abs(d - degree))
        else:
            degree += int(rng.choice((-2, -1, -1, 1, 1, 2)))
        degree = int(np.clip(degree, 0, 10))
        if cadence and i == len(rhythm) - 1:
            degree = 7 if degree > 3 else 0  # cerrar en la tónica
        notes.append((onset, length, degree))
    return notes, degree


def _compose_melody(rng, progression, bars: int):
    """Frase de 4 compases A A' B A'' que se repite: pegadiza y con cierre."""
    r_a, r_b = rng.choice(len(RHYTHMS), size=2, replace=False)
    phrase, degree = [], 4
    for bar, rhythm_idx in enumerate((r_a, r_a, r_b, r_a)):
        notes, degree = _melody_bar(rng, RHYTHMS[rhythm_idx], progression[bar], degree,
                                    cadence=bar == 3)
        phrase.append(notes)
    return [phrase[b % 4] for b in range(bars)]


def generate(seconds: float, mood: str = "cheerful", bpm: float | None = None,
             seed: int = 0) -> tuple[np.ndarray, dict]:
    if mood not in MOODS:
        raise ValueError(f"mood desconocido: {mood} (usa {', '.join(MOODS)})")
    cfg = MOODS[mood]
    rng = np.random.default_rng(seed)
    bpm = resolve_bpm(mood, bpm, seed)
    beat = 60.0 / bpm
    step16 = beat / 4
    bar_len = 4 * beat
    bars = max(2, math.ceil(seconds / bar_len) + 1)
    key = str(rng.choice(cfg.keys))
    root, scale = KEY_ROOTS[key], SCALES[cfg.scale]
    progression = cfg.progressions[int(rng.integers(len(cfg.progressions)))]
    lead = synth.INSTRUMENTS[cfg.lead]
    chord_inst = synth.INSTRUMENTS[cfg.chord_instrument]
    melody = _compose_melody(rng, progression, bars)

    buf = np.zeros((int((bars * bar_len + 2.0) * synth.SR), 2))
    for bar in range(bars):
        t_bar = bar * bar_len
        chord_root = progression[bar % len(progression)]
        chord = [_degree_midi(root - 12, scale, chord_root + i) for i in (0, 2, 4)]
        last_bar = bar == bars - 1

        # Acordes
        if cfg.chords == "strum" or last_bar:
            hits = (0,) if last_bar else (0, 4, 6, 8, 12, 14)
            for h in hits:
                for j, note in enumerate(chord):
                    place(buf, chord_inst(synth.midi_hz(note), 1.6 if last_bar else 0.9),
                          t_bar + h * step16 + j * 0.012, 0.22, pan=-0.3 + 0.3 * j)
        elif cfg.chords == "oompah":
            for h in (4, 12):
                for j, note in enumerate(chord):
                    place(buf, chord_inst(synth.midi_hz(note), 0.4), t_bar + h * step16, 0.2,
                          pan=-0.2 + 0.2 * j)
        else:  # arp
            for i in range(8):
                note = chord[i % 3] + (12 if i in (3, 7) else 0)
                place(buf, chord_inst(synth.midi_hz(note), 0.8), t_bar + i * 2 * step16, 0.2,
                      pan=-0.4 + 0.1 * (i % 8))

        # Bajo
        bass_note = _degree_midi(root - 24, scale, chord_root)
        bass_hits = (0,) if last_bar else ((0, 8) if cfg.chords != "oompah" else (0, 8))
        for h in bass_hits:
            place(buf, synth.bass(synth.midi_hz(bass_note), 1.2 if last_bar else 0.5),
                  t_bar + h * step16, 0.45)

        # Melodía (no en el compás de intro)
        if 0 < bar < bars - 1:
            for onset, length, degree in melody[bar]:
                note = _degree_midi(root, scale, degree)
                dur = max(0.25, length * step16 * 1.6)
                place(buf, lead(synth.midi_hz(note), dur), t_bar + onset * step16, 0.36, pan=0.15)
        if last_bar:
            place(buf, synth.bell(synth.midi_hz(root + 12), 2.0), t_bar, 0.25)

        # Percusión (la intro solo con hat suave)
        if cfg.drums and not last_bar:
            pattern = DRUM_PATTERNS[cfg.drums]
            for name, hits in pattern.items():
                if bar == 0 and name != "hat":
                    continue
                for h in hits:
                    place(buf, synth.DRUMS[name](rng), t_bar + h * step16, DRUM_GAINS[name],
                          pan=0.25 if name in ("hat", "shaker") else 0.0)
        elif cfg.drums and last_bar:
            place(buf, synth.kick(rng), t_bar, DRUM_GAINS["kick"])

    out = buf[: int(seconds * synth.SR)]
    peak = float(np.max(np.abs(out))) or 1.0
    out = np.tanh(1.2 * out / peak) / np.tanh(1.2) * 0.89
    info = {
        "mood": mood, "seed": seed, "bpm": bpm, "key": f"{key} {cfg.scale}",
        "duration": round(seconds, 3),
        "beats": [round(i * beat, 4) for i in range(int(seconds / beat) + 1)],
        "bars": [round(i * bar_len, 4) for i in range(int(seconds / bar_len) + 1)],
    }
    return out, info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mood", default="cheerful", choices=sorted(MOODS))
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--bpm", type=float, default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    audio, info = generate(args.seconds, args.mood, args.bpm, args.seed)
    write_wav(args.out, audio)
    args.out.with_suffix(".json").write_text(json.dumps(info, indent=1))
    print(json.dumps({k: info[k] for k in ("mood", "seed", "bpm", "key", "duration")}))


if __name__ == "__main__":
    main()
