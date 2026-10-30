"""Instrumentos y efectos de sonido sintetizados con numpy.

Todo el audio se genera aquí: no hay muestras ni derechos de terceros.
Cada función devuelve una señal mono float64 a SR muestras por segundo.
"""
import numpy as np

SR = 44100


def _t(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def midi_hz(note: float) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


def _attack(sig: np.ndarray, ms: float = 3) -> np.ndarray:
    n = min(len(sig), int(SR * ms / 1000))
    if n:
        sig[:n] *= np.linspace(0, 1, n)
    return sig


def _noise(dur: float, rng: np.random.Generator) -> np.ndarray:
    return rng.uniform(-1, 1, int(dur * SR))


def _highpass(x: np.ndarray) -> np.ndarray:
    return np.diff(x, prepend=0.0)


def _lowpass(x: np.ndarray, width: int) -> np.ndarray:
    return np.convolve(x, np.ones(width) / width, mode="same")


# --- Instrumentos -----------------------------------------------------------------

def pluck(freq: float, dur: float, brightness: float = 1.0) -> np.ndarray:
    """Cuerda pulsada tipo ukelele: armónicos que se apagan antes cuanto más agudos."""
    t = _t(dur)
    sig = np.zeros_like(t)
    for k in range(1, 9):
        if freq * k > SR / 2:
            break
        sig += np.sin(2 * np.pi * freq * k * t) / k ** 1.3 * np.exp(-t * (2.5 + k * 1.6 * brightness))
    return _attack(sig)


def pizz(freq: float, dur: float) -> np.ndarray:
    return pluck(freq, min(dur, 0.35), brightness=2.2)


def marimba(freq: float, dur: float) -> np.ndarray:
    t = _t(dur)
    sig = (np.sin(2 * np.pi * freq * t) * np.exp(-t * 5)
           + 0.35 * np.sin(2 * np.pi * freq * 4 * t) * np.exp(-t * 22)
           + 0.12 * np.sin(2 * np.pi * freq * 9.9 * t) * np.exp(-t * 45))
    return _attack(sig, 2)


def bell(freq: float, dur: float) -> np.ndarray:
    t = _t(dur)
    partials = ((1.0, 1.0, 2.2), (2.76, 0.45, 4.0), (5.4, 0.25, 7.0), (8.93, 0.12, 11.0))
    sig = sum(a * np.sin(2 * np.pi * freq * r * t) * np.exp(-t * d) for r, a, d in partials)
    return _attack(sig, 2)


def bass(freq: float, dur: float) -> np.ndarray:
    t = _t(dur)
    sig = (np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(2 * np.pi * freq * 2 * t)) * np.exp(-t * 3.5)
    return _attack(sig, 6)


INSTRUMENTS = {"pluck": pluck, "pizz": pizz, "marimba": marimba, "bell": bell, "bass": bass}


# --- Percusión ----------------------------------------------------------------------

def kick(rng: np.random.Generator) -> np.ndarray:
    t = _t(0.35)
    freq = 45 + 75 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 9)


def clap(rng: np.random.Generator) -> np.ndarray:
    t = _t(0.22)
    return (0.6 * _highpass(_noise(0.22, rng)) * np.exp(-t * 22)
            + 0.3 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 35))


def hat(rng: np.random.Generator) -> np.ndarray:
    t = _t(0.06)
    return 0.5 * _highpass(_highpass(_noise(0.06, rng))) * np.exp(-t * 70)


def shaker(rng: np.random.Generator) -> np.ndarray:
    t = _t(0.09)
    return 0.35 * _highpass(_noise(0.09, rng)) * np.sin(np.pi * t / 0.09) ** 2


DRUMS = {"kick": kick, "clap": clap, "hat": hat, "shaker": shaker}


# --- Efectos de sonido (para remates cómicos) ---------------------------------------

def _sweep(f0: float, f1: float, dur: float, vibrato: float = 0.0) -> np.ndarray:
    t = _t(dur)
    freq = f0 * (f1 / f0) ** (t / dur) * (1 + vibrato * np.sin(2 * np.pi * 9 * t))
    return np.sin(2 * np.pi * np.cumsum(freq) / SR)


def sfx_pop(rng):
    t = _t(0.09)
    return _sweep(380, 1300, 0.09) * np.exp(-t * 40)


def sfx_boing(rng):
    t = _t(0.7)
    freq = 160 * (1 + 0.6 * np.sin(2 * np.pi * 16 * t) * np.exp(-t * 4)) * (1 + t)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 4)


def sfx_whoosh(rng):
    t = _t(0.55)
    noise = _lowpass(_highpass(_noise(0.55, rng)), 6)
    return 1.6 * noise * np.sin(np.pi * t / 0.55) ** 3


def sfx_ding(rng):
    return bell(midi_hz(91), 1.4)


def sfx_tada(rng):
    out = np.zeros(int(1.6 * SR))
    for i, note in enumerate((72, 76, 79, 84)):
        sig = bell(midi_hz(note), 1.6 - i * 0.07)
        start = int(i * 0.07 * SR)
        out[start:start + len(sig)] += sig[: len(out) - start]
    return out


def sfx_bonk(rng):
    t = _t(0.3)
    return marimba(110, 0.3) + 0.4 * _highpass(_noise(0.3, rng)) * np.exp(-t * 90)


def sfx_slide_up(rng):
    t = _t(0.6)
    return _sweep(350, 1500, 0.6, vibrato=0.03) * np.sin(np.pi * t / 0.6) ** 0.5


def sfx_slide_down(rng):
    t = _t(0.6)
    return _sweep(1500, 300, 0.6, vibrato=0.03) * np.sin(np.pi * t / 0.6) ** 0.5


def sfx_sparkle(rng):
    out = np.zeros(int(0.9 * SR))
    for _ in range(7):
        start = int(rng.uniform(0, 0.4) * SR)
        sig = 0.4 * bell(rng.uniform(2200, 4200), 0.5)
        out[start:start + len(sig)] += sig[: len(out) - start]
    return out


# --- Estilo tele japonesa (variety show / anime) ----------------------------------------

def _tone(freq: float, dur: float, decay: float, harmonics: int = 3) -> np.ndarray:
    t = _t(dur)
    sig = sum(np.sin(2 * np.pi * freq * k * t) / k ** 1.5 for k in range(1, harmonics + 1))
    return _attack(sig * np.exp(-t * decay), 1)


def _sequence(parts: list[tuple[float, np.ndarray]], dur: float) -> np.ndarray:
    out = np.zeros(int(dur * SR))
    for start, sig in parts:
        s = int(start * SR)
        out[s:s + len(sig)] += sig[: max(0, len(out) - s)]
    return out


def sfx_jp_pikon(rng):
    """ピコン: el blip de dos notas que acompaña a un cartel en la tele japonesa."""
    return _sequence([(0.0, _tone(1318.5, 0.09, 30)), (0.075, _tone(1975.5, 0.22, 16))], 0.32)


def sfx_jp_pon(rng):
    """ポン: una nota redonda y suave (cartel tranquilo)."""
    return _sequence([(0.0, _tone(880.0, 0.3, 14, 2)), (0.0, 0.4 * _tone(1760.0, 0.2, 22, 1))],
                     0.32)


def sfx_jp_kiran(rng):
    """キラン: destello corto y agudo (cartel con guiño)."""
    return 0.8 * _sequence([(0.0, bell(2637.0, 0.35)), (0.06, bell(3951.0, 0.45))], 0.5)


def sfx_jp_puyon(rng):
    """ぷよん: burbuja blandita (cartel tonto, cuqui)."""
    t = _t(0.22)
    freq = 520 + 380 * np.sin(np.pi * t / 0.22)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.sin(np.pi * t / 0.22) ** 0.5


def sfx_jp_kira(rng):
    """キラッ: brillo ascendente (algo bonito, gato guapo)."""
    notes = (2093.0, 2637.0, 3136.0, 4186.0)
    return 0.7 * _sequence([(i * 0.045, bell(f, 0.5)) for i, f in enumerate(notes)], 0.75)


def sfx_jp_don(rng):
    """ドン: golpe de taiko para el remate."""
    t = _t(0.6)
    body = np.sin(2 * np.pi * np.cumsum(70 + 60 * np.exp(-t * 25)) / SR) * np.exp(-t * 7)
    skin = 0.35 * _lowpass(_noise(0.6, rng), 12) * np.exp(-t * 40)
    return body + skin


def sfx_jp_chanchan(rng):
    """ちゃんちゃん: dos acordes cortos de cierre ("y fin")."""
    def chord(root):
        return sum(_tone(root * r, 0.25, 14, 5) for r in (1.0, 1.26, 1.5)) / 3
    return _sequence([(0.0, chord(523.3)), (0.16, chord(523.3) * 1.1)], 0.45)


def sfx_jp_pyon(rng):
    """ぴょん: saltito rápido hacia arriba."""
    t = _t(0.25)
    return _sweep(300, 1400, 0.25, vibrato=0.05) * np.exp(-t * 6)


def sfx_jp_hyuu(rng):
    """ヒューッ: silbido que cae (fallo, caída, decepción)."""
    t = _t(0.7)
    return 0.8 * _sweep(1900, 500, 0.7, vibrato=0.02) * np.sin(np.pi * t / 0.7) ** 0.7


def sfx_jp_tehe(rng):
    """てへ: tres notas cuquis bajando (travesura inocente)."""
    notes = (1318.5, 1046.5, 880.0)
    return _sequence([(i * 0.09, marimba(f, 0.3)) for i, f in enumerate(notes)], 0.5)


def sfx_jp_zun(rng):
    """ズーン: bajón grave (cansancio, drama, "oh no")."""
    t = _t(0.9)
    saw = sum(np.sin(2 * np.pi * 55 * k * t) / k for k in range(1, 12))
    return 0.6 * saw * np.exp(-t * 3) * np.minimum(1, t / 0.02)


def sfx_jp_shakin(rng):
    """シャキーン: destello metálico (momento heroico, "listo")."""
    t = _t(0.5)
    metal = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * d)
                for f, d in ((2960, 6), (4430, 8), (5920, 10)))
    return 0.4 * metal + 0.3 * _highpass(_noise(0.5, rng)) * np.exp(-t * 30)


SFX = {
    "pop": sfx_pop, "boing": sfx_boing, "whoosh": sfx_whoosh, "ding": sfx_ding,
    "tada": sfx_tada, "bonk": sfx_bonk, "slide_up": sfx_slide_up,
    "slide_down": sfx_slide_down, "sparkle": sfx_sparkle,
    "jp_pikon": sfx_jp_pikon, "jp_kira": sfx_jp_kira, "jp_don": sfx_jp_don,
    "jp_chanchan": sfx_jp_chanchan, "jp_pyon": sfx_jp_pyon, "jp_hyuu": sfx_jp_hyuu,
    "jp_tehe": sfx_jp_tehe, "jp_zun": sfx_jp_zun, "jp_shakin": sfx_jp_shakin,
    "jp_pon": sfx_jp_pon, "jp_kiran": sfx_jp_kiran, "jp_puyon": sfx_jp_puyon,
}

# Sonidos "de cartel": se rotan para que dos carteles seguidos no suenen igual.
CARTEL_SFX = ("jp_pikon", "jp_pon", "jp_kiran", "jp_puyon")
