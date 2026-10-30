"""Lectura/escritura WAV y mezcla estéreo en numpy."""
import wave
from pathlib import Path

import numpy as np

from .media import probe, run_ffmpeg
from .synth import SR


def db(value: float) -> float:
    return 10 ** (value / 20)


def silence(seconds: float) -> np.ndarray:
    return np.zeros((int(round(seconds * SR)), 2))


def write_wav(path: Path, stereo: np.ndarray) -> None:
    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(SR)
        out.writeframes(pcm.tobytes())


def read_wav(path: Path) -> np.ndarray:
    raw = run_ffmpeg(["-i", str(path), "-f", "s16le", "-ac", "2", "-ar", str(SR), "-"],
                     capture=True)
    return np.frombuffer(raw, dtype="<i2").reshape(-1, 2) / 32767.0


def place(buf: np.ndarray, mono: np.ndarray, t: float, gain: float = 1.0,
          pan: float = 0.0) -> None:
    """Suma una señal mono en buf (estéreo) a partir del segundo t. pan en [-1, 1]."""
    start = int(round(t * SR))
    if start >= len(buf) or start < 0:
        return
    sig = mono[: len(buf) - start] * gain
    angle = (pan + 1) * np.pi / 4
    buf[start:start + len(sig), 0] += sig * np.cos(angle)
    buf[start:start + len(sig), 1] += sig * np.sin(angle)


def add_stereo(buf: np.ndarray, stereo: np.ndarray, t: float, gain: float = 1.0) -> None:
    """Suma una señal estéreo en buf a partir del segundo t (recorta lo que sobre)."""
    start = int(round(t * SR))
    if start >= len(buf) or start < 0:
        return
    sig = stereo[: len(buf) - start] * gain
    buf[start:start + len(sig)] += sig


def duck_envelope(n_samples: int, windows: list[tuple[float, float]], depth_db: float,
                  ramp_s: float = 0.15) -> np.ndarray:
    """Ganancia por muestra: 1 fuera de las ventanas y db(depth_db) dentro, con rampas."""
    active = np.zeros(n_samples)
    for t0, t1 in windows:
        active[max(0, int(t0 * SR)):min(n_samples, int(t1 * SR))] = 1.0
    if windows:
        ramp = max(1, int(ramp_s * SR))
        active = np.clip(np.convolve(active, np.ones(ramp) / ramp, mode="same"), 0, 1)
    return 1.0 - active * (1.0 - db(depth_db))


def _atempo_chain(speed: float) -> str:
    """atempo solo acepta [0.5, 2]; se encadena para otros valores."""
    parts = []
    while speed > 2.0:
        parts.append("atempo=2.0")
        speed /= 2.0
    while speed < 0.5:
        parts.append("atempo=0.5")
        speed /= 0.5
    parts.append(f"atempo={speed:.4f}")
    return ",".join(parts)


def segment_audio(src: Path, start: float, end: float, speed: float) -> np.ndarray:
    """Audio original del tramo (ya acelerado/ralentizado); silencio si no tiene."""
    out_dur = (end - start) / speed
    if not probe(src).has_audio:
        return silence(out_dur)
    raw = run_ffmpeg(["-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", str(src),
                      "-vn", "-af", _atempo_chain(speed), "-f", "s16le", "-ac", "2",
                      "-ar", str(SR), "-"], capture=True)
    audio = np.frombuffer(raw, dtype="<i2").reshape(-1, 2) / 32767.0
    target = silence(out_dur)
    n = min(len(audio), len(target))
    target[:n] = audio[:n]
    return target


def fade_out(stereo: np.ndarray, seconds: float) -> np.ndarray:
    n = min(len(stereo), int(seconds * SR))
    out = stereo.copy()
    if n:
        out[-n:] *= np.linspace(1, 0, n)[:, None]
    return out


def is_silent(stereo: np.ndarray) -> bool:
    return float(np.max(np.abs(stereo))) < 1e-4 if len(stereo) else True
