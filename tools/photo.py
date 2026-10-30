"""Prepara una foto para post o carrusel: recorte 4:5 (o 1:1), color suave y rótulo opcional.

Uso: .venv/bin/python -m tools.photo inbox/<post>/02.jpg --out <out_dir>/02.jpg
     [--cx 0.5 --cy 0.5 --zoom 1.0] [--aspect 4:5] [--text "im hidimg" --style label
     --look sticker --y 0.8]

HEIC se convierte con sips. Al guardar con Pillow se pierden los metadatos (GPS incluido).
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

from . import textcard

ASPECTS = {"4:5": (1080, 1350), "1:1": (1080, 1080), "9:16": (1080, 1920)}


def _open(src: Path) -> Image.Image:
    if src.suffix.lower() in (".heic", ".heif"):
        with tempfile.TemporaryDirectory() as tmp:
            jpg = Path(tmp) / "converted.jpg"
            subprocess.run(["sips", "-s", "format", "jpeg", str(src), "--out", str(jpg)],
                           check=True, capture_output=True)
            return ImageOps.exif_transpose(Image.open(jpg)).convert("RGB")
    return ImageOps.exif_transpose(Image.open(src)).convert("RGB")


def crop(img: Image.Image, size: tuple[int, int], cx: float, cy: float,
         zoom: float) -> Image.Image:
    aspect = size[0] / size[1]
    w = min(img.width, img.height * aspect) / max(1.0, zoom)
    h = w / aspect
    left = min(max(0, cx * img.width - w / 2), img.width - w)
    top = min(max(0, cy * img.height - h / 2), img.height - h)
    return img.crop((int(left), int(top), int(left + w), int(top + h))).resize(
        size, Image.LANCZOS)


def prepare(src: Path, out: Path, aspect: str = "4:5", cx: float = 0.5, cy: float = 0.5,
            zoom: float = 1.0, text: str = "", style: str = "label", look: str = "outline",
            y: float | None = None) -> Path:
    size = ASPECTS[aspect]
    img = crop(_open(src), size, cx, cy, zoom)
    img = ImageEnhance.Contrast(ImageEnhance.Color(img).enhance(1.1)).enhance(1.05)
    if text:
        card = textcard.render(text, style, look, size, y=y)
        img = Image.alpha_composite(img.convert("RGBA"), card).convert("RGB")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=92)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--aspect", default="4:5", choices=sorted(ASPECTS))
    parser.add_argument("--cx", type=float, default=0.5)
    parser.add_argument("--cy", type=float, default=0.5)
    parser.add_argument("--zoom", type=float, default=1.0)
    parser.add_argument("--text", default="")
    parser.add_argument("--style", default="label", choices=sorted(textcard.STYLES))
    parser.add_argument("--look", default="outline", choices=textcard.LOOKS)
    parser.add_argument("--y", type=float, default=None)
    args = parser.parse_args()
    print(prepare(args.src, args.out, args.aspect, args.cx, args.cy, args.zoom, args.text,
                  args.style, args.look, args.y))


if __name__ == "__main__":
    main()
