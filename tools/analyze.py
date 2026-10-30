"""Analiza un vídeo para decidir el montaje: movimiento, brillo, sonido, cambios de plano
y hojas de contactos con marcas de tiempo (para mirarlas con Read).

Uso: .venv/bin/python -m tools.analyze inbox/<post>/01.mp4 [--step 0.5]
Escribe inbox/<post>/_analysis/<archivo>/analysis.json y sheet_NN.jpg.
"""
import argparse
import json
import re
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .media import ffmpeg_metadata, probe, run_ffmpeg

DEFAULT_STEP_S = 0.5
MAX_FRAMES = 120
SHEET_COLS, SHEET_ROWS = 5, 4
LABEL_FONT = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"
_PTS = re.compile(r"pts_time:([\d.]+)")
_KV = re.compile(r"lavfi\.([\w.]+)=(-?[\d.]+|-?inf|nan)")


def _parse_metadata(text: str) -> list[tuple[float, dict[str, float]]]:
    rows: list[tuple[float, dict[str, float]]] = []
    for line in text.splitlines():
        if m := _PTS.search(line):
            rows.append((float(m.group(1)), {}))
        elif (m := _KV.search(line)) and rows:
            value = float(m.group(2)) if m.group(2) not in ("inf", "-inf", "nan") else -70.0
            rows[-1][1][m.group(1)] = value
    return rows


def _bucket(rows, key: str, step: float, duration: float, reducer=max) -> list[float | None]:
    buckets: list[list[float]] = [[] for _ in range(int(duration / step) + 1)]
    for t, values in rows:
        if key in values and int(t / step) < len(buckets):
            buckets[int(t / step)].append(values[key])
    return [reducer(b) if b else None for b in buckets]


def _normalize(values: list[float | None]) -> list[float | None]:
    present = [v for v in values if v is not None]
    if not present or max(present) == min(present):
        return [0.0 if v is not None else None for v in values]
    lo, hi = min(present), max(present)
    return [round((v - lo) / (hi - lo), 2) if v is not None else None for v in values]


def motion_and_brightness(src: Path, step: float, duration: float):
    text = ffmpeg_metadata(["-i", str(src), "-vf",
                            "fps=4,scale=160:-2,signalstats,metadata=mode=print:file=-", "-an"])
    rows = _parse_metadata(text)
    motion = _normalize(_bucket(rows, "signalstats.YDIF", step, duration))
    bright = _bucket(rows, "signalstats.YAVG", step, duration, lambda b: sum(b) / len(b))
    return motion, [round(b / 255, 2) if b is not None else None for b in bright]


def loudness(src: Path, step: float, duration: float) -> list[float | None]:
    text = ffmpeg_metadata(["-i", str(src), "-vn", "-af",
                            "ebur128=metadata=1,ametadata=mode=print:key=lavfi.r128.M:file=-"])
    values = _bucket(_parse_metadata(text), "r128.M", step, duration)
    return [round(v, 1) if v is not None else None for v in values]


def scene_changes(src: Path) -> list[float]:
    text = ffmpeg_metadata(["-i", str(src), "-an", "-vf",
                            "scale=320:-2,scdet=threshold=12,metadata=mode=print:file=-"])
    return [round(t, 2) for t, values in _parse_metadata(text) if "scd.time" in values]


def contact_sheets(src: Path, out_dir: Path, step: float, width: int, height: int) -> list[str]:
    thumb_w, thumb_h = (216, 384) if height >= width else (384, 216)
    font = ImageFont.truetype(LABEL_FONT, 26)
    with tempfile.TemporaryDirectory() as tmp:
        run_ffmpeg(["-i", str(src), "-vf", f"fps=1/{step},scale={thumb_w}:{thumb_h}",
                    f"{tmp}/f_%04d.jpg"])
        frames = sorted(Path(tmp).glob("f_*.jpg"))
        per_sheet = SHEET_COLS * SHEET_ROWS
        sheets = []
        for s in range(0, len(frames), per_sheet):
            sheet = Image.new("RGB", (SHEET_COLS * thumb_w, SHEET_ROWS * (thumb_h + 34)), "black")
            draw = ImageDraw.Draw(sheet)
            for i, frame in enumerate(frames[s:s + per_sheet]):
                x = (i % SHEET_COLS) * thumb_w
                y = (i // SHEET_COLS) * (thumb_h + 34)
                sheet.paste(Image.open(frame), (x, y + 34))
                draw.text((x + 8, y + 3), f"{(s + i) * step:.1f}s", font=font, fill="yellow")
            path = out_dir / f"sheet_{s // per_sheet + 1:02d}.jpg"
            sheet.save(path, quality=80)
            sheets.append(path.name)
    return sheets


def analyze(src: Path, step: float | None = None) -> dict:
    info = probe(src)
    step = step or max(DEFAULT_STEP_S, round(info.duration / MAX_FRAMES, 1))
    out_dir = src.parent / "_analysis" / src.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    motion, bright = motion_and_brightness(src, step, info.duration)
    loud = loudness(src, step, info.duration) if info.has_audio else [None] * len(motion)
    timeline = [
        {"t": round(i * step, 2), "motion": m, "brightness": b, "loudness": l}
        for i, (m, b, l) in enumerate(zip(motion, bright, loud))
    ]
    result = {
        "source": str(src),
        "duration": round(info.duration, 2),
        "width": info.width,
        "height": info.height,
        "fps": round(info.fps, 2),
        "has_audio": info.has_audio,
        "step": step,
        "scene_changes": scene_changes(src),
        "timeline": timeline,
        "sheets": contact_sheets(src, out_dir, step, info.width, info.height),
        "analysis_dir": str(out_dir),
    }
    (out_dir / "analysis.json").write_text(json.dumps(result, indent=1))
    return result


def _summary(result: dict) -> str:
    lines = [f"{k}: {result[k]}" for k in
             ("source", "duration", "width", "height", "fps", "has_audio", "scene_changes",
              "analysis_dir", "sheets")]
    lines.append("t      motion  bright  loud(LUFS)")
    for row in result["timeline"]:
        lines.append(f"{row['t']:<6} {row['motion']!s:<7} {row['brightness']!s:<7} {row['loudness']}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src", type=Path)
    parser.add_argument("--step", type=float, default=None)
    args = parser.parse_args()
    print(_summary(analyze(args.src, args.step)))


if __name__ == "__main__":
    main()
