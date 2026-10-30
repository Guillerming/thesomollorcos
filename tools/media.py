"""Utilidades comunes sobre ffprobe/ffmpeg."""
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}


@dataclass(frozen=True)
class Probe:
    duration: float
    width: int  # ya con la rotación aplicada (ffmpeg autorrota al decodificar)
    height: int
    fps: float
    has_audio: bool


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def probe(path: Path) -> Probe:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format",
         str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(out)
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    rotation = 0
    for side in video.get("side_data_list", []):
        rotation = int(side.get("rotation", rotation))
    width, height = video["width"], video["height"]
    if abs(rotation) in (90, 270):
        width, height = height, width
    num, den = video.get("avg_frame_rate", "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    return Probe(
        duration=float(data["format"].get("duration", 0.0)),
        width=width,
        height=height,
        fps=fps,
        has_audio=any(s["codec_type"] == "audio" for s in data["streams"]),
    )


def run_ffmpeg(args: list[str], capture: bool = False) -> bytes:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg falló: {result.stderr.decode(errors='replace')[-1500:]}")
    return result.stdout if capture else b""


def ffmpeg_metadata(args: list[str]) -> str:
    """Ejecuta ffmpeg con un filtro metadata=print:file=- y devuelve lo impreso."""
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", *args, "-f", "null", "-"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg falló: {result.stderr[-1500:]}")
    return result.stdout
