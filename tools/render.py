"""Renderiza un EDL: tramos recortados, color, rótulos, música original y efectos.

Uso: .venv/bin/python -m tools.render inbox/<post>/edl.json

Salidas en out_dir: el vídeo principal (con música) y, si se pide, una versión sin música
para poner un audio en tendencia desde la app. Escribe render_report.json con los tiempos
finales (útil para elegir la portada).
"""
import argparse
import json
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from . import music as music_mod
from . import textcard, voice
from .audio import (add_stereo, db, duck_envelope, fade_out, is_silent, place, read_wav,
                    segment_audio, silence, write_wav)
from .edl import (VOICE_PAD_MAX_S, VOICE_PAD_MIN_S, Edl, Line, Text, crop_filter,
                  fit_voice_segments, load, reading_time, resolve_text_sfx, segment_starts,
                  snap_to_beats)
from .media import probe, run_ffmpeg
from .synth import CARTEL_SFX, SFX, SR

ROOT = Path(__file__).resolve().parent.parent
SUBTITLE_TAIL_S = 0.3  # el subtítulo se queda un poco más que la voz
TEXT_FADE_S = 0.12
MUSIC_FADE_S = 1.2
LOUDNORM = "loudnorm=I=-14:TP=-1.5:LRA=11"


def _color_filter(color: dict) -> str:
    return ("eq=" + ":".join(f"{k}={color.get(k, d)}" for k, d in
                             (("contrast", 1.05), ("saturation", 1.12), ("brightness", 0.0),
                              ("gamma", 1.0))))


def _text_windows(edl: Edl, starts: list[float], total: float) -> list[tuple[float, float]]:
    """Ventana (inicio, fin) de cada rótulo. Si dos del mismo estilo se pisan (ocupan el mismo
    sitio en pantalla), el anterior termina justo cuando empieza el siguiente."""
    windows = []
    for text in edl.texts:
        t0 = min(starts[text.segment] + text.at, total - 0.2)
        windows.append([round(t0, 3), round(min(t0 + text.dur, total), 3)])
    for i, text in enumerate(edl.texts):
        later = [windows[j][0] for j, other in enumerate(edl.texts)
                 if other.style == text.style and windows[j][0] > windows[i][0]]
        if later and min(later) < windows[i][1]:
            windows[i][1] = round(min(later) - 0.02, 3)
    return [(a, b) for a, b in windows]


def render_video(edl: Edl, starts: list[float], total: float, work: Path) -> Path:
    args: list[str] = []
    for seg in edl.segments:
        args += ["-ss", f"{seg.start:.3f}", "-t", f"{seg.end - seg.start:.3f}", "-i", str(seg.src)]
    windows = _text_windows(edl, starts, total)
    for k, (text, (t0, t1)) in enumerate(zip(edl.texts, windows)):
        png = work / f"text_{k:02d}.png"
        textcard.render(text.text, text.style, text.look, (edl.width, edl.height)).save(png)
        args += ["-loop", "1", "-framerate", str(edl.fps), "-t", f"{t1 - t0:.3f}", "-i", str(png)]

    n = len(edl.segments)
    chains = [
        f"[{i}:v]setpts=(PTS-STARTPTS)/{seg.speed},{crop_filter(seg, edl.width, edl.height)},"
        f"scale={edl.width}:{edl.height}:flags=lanczos,fps={edl.fps},setsar=1,format=yuv420p[v{i}]"
        for i, seg in enumerate(edl.segments)
    ]
    chains.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[base]")
    chains.append(f"[base]{_color_filter(edl.color)}[c0]")
    for k, (t0, t1) in enumerate(windows):
        dur = t1 - t0
        chains.append(
            f"[{n + k}:v]format=rgba,fade=t=in:st=0:d={TEXT_FADE_S}:alpha=1,"
            f"fade=t=out:st={max(0.0, dur - TEXT_FADE_S):.3f}:d={TEXT_FADE_S}:alpha=1,"
            f"setpts=PTS-STARTPTS+{t0}/TB[tx{k}]")
        chains.append(f"[c{k}][tx{k}]overlay=0:0:eof_action=pass:"
                      f"enable='between(t,{t0},{t1})'[c{k + 1}]")
    chains.append(f"[c{len(windows)}]format=yuv420p[vout]")

    out = work / "video.mp4"
    run_ffmpeg([*args, "-filter_complex", ";".join(chains), "-map", "[vout]", "-an",
                "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-profile:v", "high", "-pix_fmt", "yuv420p", str(out)])
    return out


@dataclass(frozen=True)
class SpokenLine:
    line: Line
    audio: np.ndarray
    start: float

    @property
    def end(self) -> float:
        return self.start + len(self.audio) / SR


def synthesize_audio(edl: Edl) -> list[np.ndarray]:
    return [read_wav(voice.synthesize(line.cat, line.text)) for line in edl.lines]


def place_lines(edl: Edl, audios: list[np.ndarray], starts: list[float]) -> list[SpokenLine]:
    return [SpokenLine(line, audio, starts[line.segment] + line.at)
            for line, audio in zip(edl.lines, audios)]


def voice_padding(edl: Edl, spoken: list[SpokenLine], starts: list[float]) -> list[dict]:
    report = []
    for s in spoken:
        seg_end = starts[s.line.segment] + edl.segments[s.line.segment].out_dur
        before, after = s.start - starts[s.line.segment], seg_end - s.end
        ok = all(VOICE_PAD_MIN_S - 0.02 <= p <= VOICE_PAD_MAX_S + 0.02 for p in (before, after))
        report.append({"pad_before": round(before, 3), "pad_after": round(after, 3),
                       "pad_ok": ok})
    return report


def subtitle_texts(spoken: list[SpokenLine]) -> tuple[Text, ...]:
    return tuple(
        Text(text=s.line.subtitle, segment=s.line.segment, at=s.line.at,
             dur=round(s.end - s.start + SUBTITLE_TAIL_S, 3), style=s.line.subtitle_style,
             look=s.line.subtitle_look, sfx=None)  # el blip pisaría la voz
        for s in spoken if s.line.subtitle
    )


def build_mixes(edl: Edl, starts: list[float], total: float, bpm: float | None,
                spoken: list[SpokenLine] = ()):
    original = np.concatenate([segment_audio(s.src, s.start, s.end, s.speed)
                               for s in edl.segments]) * db(edl.original_audio_db)
    base = silence(total)
    n = min(len(base), len(original))
    base[:n] += original[:n]

    rng = np.random.default_rng(0)
    for fx in edl.sfx:
        if fx.name not in SFX:
            raise ValueError(f"sfx desconocido: {fx.name} (usa {', '.join(SFX)})")
        place(base, SFX[fx.name](rng), starts[fx.segment] + fx.at, db(fx.gain_db))
    names = resolve_text_sfx(edl, CARTEL_SFX)
    for text, name, (t0, _) in zip(edl.texts, names, _text_windows(edl, starts, total)):
        if name:  # el sonido del cartel, justo cuando aparece
            if name not in SFX:
                raise ValueError(f"sfx desconocido en '{text.text}': {name}")
            place(base, SFX[name](rng), t0, db(text.sfx_gain_db))
    for s in spoken:  # la voz es contenido: va también en la versión sin música
        add_stereo(base, s.audio, s.start, db(s.line.gain_db))

    clean = base.copy()
    if edl.music is None:
        return base, clean, None
    song, info = music_mod.generate(total + 0.5, edl.music.mood, bpm, edl.music.seed)
    song = fade_out(song[: len(base)], MUSIC_FADE_S)
    ducking = duck_envelope(len(song), [(s.start, s.end) for s in spoken], edl.duck_db)
    main = base.copy()
    main[: len(song)] += song * db(edl.music.gain_db) * ducking[:, None]
    return main, clean, info


def mux(video: Path, mix: np.ndarray, out: Path, work: Path, normalize: bool = True) -> None:
    """normalize=False deja el nivel tal cual: en la versión sin música con solo efectos,
    normalizar los subiría al volumen de una canción."""
    wav = work / f"{out.stem}.wav"
    write_wav(wav, mix)
    audio_filter = ["-af", LOUDNORM] if normalize and not is_silent(mix) else []
    run_ffmpeg(["-i", str(video), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", *audio_filter, "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                "-shortest", "-movflags", "+faststart", str(out)])


def render(edl_path: Path) -> dict:
    durations: dict[Path, float] = {}
    raw = json.loads(edl_path.read_text())
    for s in raw.get("segments", []):
        src = Path(s["src"]) if Path(s["src"]).is_absolute() else ROOT / s["src"]
        if src.exists():
            durations[src] = probe(src).duration
    edl = load(edl_path, ROOT, durations)

    # 1) Voces primero: hace falta saber cuánto duran para dejarles margen en su tramo.
    audios = synthesize_audio(edl)
    if edl.lines:
        segments, lines = fit_voice_segments(edl.segments, edl.lines,
                                             [len(a) / SR for a in audios], durations)
        edl = replace(edl, segments=segments, lines=lines)
    # 2) Beat, sin tocar los tramos con voz.
    bpm = None
    if edl.music:
        bpm = music_mod.resolve_bpm(edl.music.mood, edl.music.bpm, edl.music.seed)
        if edl.snap_to_beats:
            keep = {line.segment for line in edl.lines}
            edl = replace(edl, segments=snap_to_beats(edl.segments, bpm, durations, keep))
    # 3) Tiempos finales.
    starts = segment_starts(edl.segments)
    total = sum(s.out_dur for s in edl.segments)
    spoken = place_lines(edl, audios, starts)
    edl = replace(edl, texts=edl.texts + subtitle_texts(spoken))

    edl.out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        video = render_video(edl, starts, total, work)
        main_mix, clean_mix, music_info = build_mixes(edl, starts, total, bpm, spoken)
        mux(video, main_mix, edl.out_dir / edl.main, work)
        if edl.clean:
            has_original = any(probe(s.src).has_audio for s in edl.segments)
            mux(video, clean_mix, edl.out_dir / edl.clean, work, normalize=has_original)

    windows = _text_windows(edl, starts, total)
    sfx_names = resolve_text_sfx(edl, CARTEL_SFX)
    padding = voice_padding(edl, spoken, starts)
    report = {
        "duration": round(total, 3),
        "bpm": bpm,
        "music": {k: music_info[k] for k in ("mood", "seed", "bpm", "key")} if music_info else None,
        "segments": [{"src": str(s.src), "start": s.start, "end": s.end,
                      "out_start": round(st, 3), "out_end": round(st + s.out_dur, 3)}
                     for s, st in zip(edl.segments, starts)],
        "texts": [{"text": t.text, "start": w[0], "end": w[1], "sfx": name,
                   "too_short_to_read": w[1] - w[0] < reading_time(t.text, t.style) - 0.05}
                  for t, w, name in zip(edl.texts, windows, sfx_names)],
        "lines": [{"cat": s.line.cat, "text": s.line.text, "start": round(s.start, 3),
                   "end": round(s.end, 3), "overruns_video": s.end > total + 0.05, **pad}
                  for s, pad in zip(spoken, padding)],
        "outputs": [edl.main] + ([edl.clean] if edl.clean else []),
    }
    (edl_path.parent / "render_report.json").write_text(json.dumps(report, indent=1))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edl", type=Path)
    args = parser.parse_args()
    print(json.dumps(render(args.edl), indent=1))


if __name__ == "__main__":
    main()
