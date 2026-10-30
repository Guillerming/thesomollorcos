"""Portada del reel: un fotograma del montaje con el mismo encuadre y un rótulo.

Uso: .venv/bin/python -m tools.cover inbox/<post>/edl.json --segment 0 --at 0.8
     --text "im hidimg" [--look outline] --out <out_dir>/cover.jpg

--at son segundos desde el inicio del tramo en la salida (como en el EDL).
El texto queda dentro del recorte 3:4 que muestra la cuadrícula del perfil.
"""
import argparse
import io
import json
from pathlib import Path

from PIL import Image, ImageEnhance

from . import textcard
from .edl import crop_filter, load
from .media import probe, run_ffmpeg

ROOT = Path(__file__).resolve().parent.parent
# Dentro del recorte 3:4 de la cuadrícula (y de 0.125 a 0.875 de la altura).
POSITIONS = {"top": 0.24, "middle": 0.45, "bottom": 0.70}


def make_cover(edl_path: Path, segment: int, at: float, text: str, look: str,
               out: Path, position: str = "top") -> Path:
    raw = json.loads(edl_path.read_text())
    durations = {}
    for s in raw["segments"]:
        src = Path(s["src"]) if Path(s["src"]).is_absolute() else ROOT / s["src"]
        durations[src] = probe(src).duration
    edl = load(edl_path, ROOT, durations)
    seg = edl.segments[segment]
    t = min(seg.start + at * seg.speed, seg.end - 0.05)

    png = run_ffmpeg(["-ss", f"{t:.3f}", "-i", str(seg.src), "-frames:v", "1", "-vf",
                      f"{crop_filter(seg, edl.width, edl.height)},"
                      f"scale={edl.width}:{edl.height}:flags=lanczos",
                      "-f", "image2pipe", "-vcodec", "png", "-"], capture=True)
    frame = Image.open(io.BytesIO(png)).convert("RGB")
    frame = ImageEnhance.Contrast(ImageEnhance.Color(frame).enhance(1.12)).enhance(1.05)
    if text:
        card = textcard.render(text, "cover", look, frame.size, y=POSITIONS[position])
        frame = Image.alpha_composite(frame.convert("RGBA"), card).convert("RGB")
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.save(out, quality=92)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edl", type=Path)
    parser.add_argument("--segment", type=int, default=0)
    parser.add_argument("--at", type=float, default=0.5)
    parser.add_argument("--text", default="")
    parser.add_argument("--look", default="outline", choices=textcard.LOOKS)
    parser.add_argument("--position", default="top", choices=sorted(POSITIONS),
                        help="dónde va el texto: donde NO esté el gato")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(make_cover(args.edl, args.segment, args.at, args.text, args.look, args.out,
                     args.position))


if __name__ == "__main__":
    main()
