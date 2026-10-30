"""Voces de los gatos con Voicebox (servidor local en http://127.0.0.1:17493).

Cada gato con voz tiene una ficha en brand/voces.json que apunta a un perfil de Voicebox
(grabado por nosotros haciendo de ese gato). Las frases generadas se guardan en caché:
la misma frase con la misma voz no se vuelve a generar.

Uso:
  .venv/bin/python -m tools.voice --list
  .venv/bin/python -m tools.voice --cat Mayoneso --text "You want to know why I am so sleepy?" \
      --out inbox/<post>/_analysis/prueba.wav
"""
import argparse
import hashlib
import json
import shutil
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICES_FILE = ROOT / "brand" / "voces.json"
CACHE_DIR = ROOT / "state" / "voice_cache"
VOICEBOX_URL = "http://127.0.0.1:17493"
GENERATE_TIMEOUT_S = 180
POLL_S = 0.5
DONE_STATUSES = {"completed", "complete", "done", "success"}
FAILED_STATUSES = {"failed", "error", "cancelled"}


class VoiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Voice:
    cat: str
    profile: str  # nombre del perfil en Voicebox
    engine: str = "chatterbox_turbo"
    effects: tuple | None = None


def load_voices(path: Path = VOICES_FILE) -> dict[str, Voice]:
    raw = json.loads(path.read_text()) if path.exists() else {}
    return {
        cat: Voice(cat, cfg["profile"], cfg.get("engine", "chatterbox_turbo"),
                   tuple(cfg["effects"]) if cfg.get("effects") else None)
        for cat, cfg in raw.items() if not cat.startswith("_")
    }


class Voicebox:
    def __init__(self, base_url: str = VOICEBOX_URL):
        self._base = base_url
        self._profile_ids: dict[str, str] = {}

    def _call(self, method: str, path: str, body: dict | None = None, timeout: float = 30):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self._base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as err:
            raise VoiceError(f"Voicebox {method} {path}: {err.code} "
                             f"{err.read().decode(errors='replace')[:300]}") from err
        except urllib.error.URLError as err:
            raise VoiceError("Voicebox no responde en "
                             f"{self._base}: ¿está abierta la app? ({err.reason})") from err

    def _json(self, method: str, path: str, body: dict | None = None):
        return json.loads(self._call(method, path, body))

    def profile_names(self) -> list[str]:
        return [p["name"] for p in self._json("GET", "/profiles")]

    def profile_id(self, name: str) -> str:
        if name not in self._profile_ids:
            matches = [p for p in self._json("GET", "/profiles") if p["name"] == name]
            if not matches:
                raise VoiceError(f"No hay perfil '{name}' en Voicebox")
            self._profile_ids[name] = matches[0]["id"]
        return self._profile_ids[name]

    def generate(self, voice: Voice, text: str, out: Path) -> Path:
        body = {"profile_id": self.profile_id(voice.profile), "text": text,
                "engine": voice.engine, "language": "en"}
        if voice.effects:
            body["effects_chain"] = list(voice.effects)
        generation = self._json("POST", "/generate", body)
        deadline = time.monotonic() + GENERATE_TIMEOUT_S
        while time.monotonic() < deadline:
            info = self._json("GET", f"/history/{generation['id']}")
            if info["status"] in DONE_STATUSES:
                out.write_bytes(self._call("GET", f"/audio/{generation['id']}", timeout=60))
                return out
            if info["status"] in FAILED_STATUSES:
                raise VoiceError(f"Voicebox no ha podido generar '{text}': {info.get('error')}")
            time.sleep(POLL_S)
        raise VoiceError(f"Voicebox tarda demasiado con '{text}'")


def cache_key(voice: Voice, text: str) -> str:
    raw = json.dumps([voice.profile, voice.engine, voice.effects, text], sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()


def synthesize(cat: str, text: str, voices: dict[str, Voice] | None = None,
               client: Voicebox | None = None, cache_dir: Path = CACHE_DIR) -> Path:
    """WAV de la frase con la voz del gato (de caché si ya existe)."""
    voices = load_voices() if voices is None else voices
    if cat not in voices:
        available = ", ".join(voices) or "ninguno"
        raise VoiceError(f"{cat} todavía no tiene voz (con voz: {available})")
    voice = voices[cat]
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{cache_key(voice, text)}.wav"
    if not cached.exists():
        tmp = cached.with_suffix(".part")
        (client or Voicebox()).generate(voice, text, tmp)
        tmp.rename(cached)
    return cached


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="gatos con voz y si Voicebox los tiene")
    parser.add_argument("--cat")
    parser.add_argument("--text")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    voices = load_voices()
    if args.list:
        try:
            names = set(Voicebox().profile_names())
            status = {cat: ("ok" if v.profile in names else f"falta el perfil '{v.profile}'")
                      for cat, v in voices.items()}
        except VoiceError as err:
            status = {cat: str(err) for cat in voices}
        print(json.dumps(status, ensure_ascii=False, indent=1))
        return
    if not (args.cat and args.text and args.out):
        parser.error("usa --list, o --cat, --text y --out")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(synthesize(args.cat, args.text, voices), args.out)
    print(args.out)


if __name__ == "__main__":
    main()
