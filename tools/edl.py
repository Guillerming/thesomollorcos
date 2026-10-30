"""Lista de decisiones de montaje (EDL): lo que decide la skill y ejecuta render.py.

Los tiempos de rótulos y efectos van anclados a un tramo (segment + at), así siguen en su
sitio aunque el ajuste al beat alargue o acorte los tramos.
"""
import json
from dataclasses import dataclass, field, replace
from pathlib import Path

MIN_SPEED, MAX_SPEED = 0.25, 4.0


@dataclass(frozen=True)
class Segment:
    src: Path
    start: float
    end: float
    speed: float = 1.0
    cx: float = 0.5  # centro del sujeto en el cuadro original (0–1)
    cy: float = 0.5
    zoom: float = 1.0  # >1 = acercar (punch-in)

    @property
    def out_dur(self) -> float:
        return (self.end - self.start) / self.speed


@dataclass(frozen=True)
class Text:
    text: str
    segment: int = 0
    at: float = 0.0  # segundos desde el inicio del tramo (en la salida)
    dur: float = 2.0
    style: str = "label"
    look: str = "outline"
    sfx: str | None = "auto"  # "auto" = el de text_sfx para su estilo; None = sin efecto
    sfx_gain_db: float = -14.0  # a -6 sonaban demasiado fuertes (feedback de Guille)


# Efecto al aparecer un cartel, por estilo (el gancho y los subtítulos de voz, sin blip).
# "@cartel" = ir rotando los sonidos de cartel (synth.CARTEL_SFX).
ROTATE = "@cartel"
DEFAULT_TEXT_SFX = {"label": ROTATE, "punch": "jp_don", "hook": None, "cover": None}

# Margen alrededor de cada narración dentro de su tramo (feedback de Guille, 29/10/2026).
VOICE_PAD_MIN_S, VOICE_PAD_MAX_S = 0.3, 0.6
VOICE_PAD_AFTER_S = 0.45
MIN_FIT_SPEED = 0.7  # se puede ralentizar hasta aquí para que quepa la frase


@dataclass(frozen=True)
class Sfx:
    name: str
    segment: int = 0
    at: float = 0.0
    gain_db: float = -6.0


@dataclass(frozen=True)
class Line:
    """Frase hablada por un gato (voz de Voicebox) con su subtítulo en voz gatuna escrita."""
    cat: str
    text: str  # lo que se dice: inglés de niño, bien escrito (ver skill voces-gatunas)
    segment: int = 0
    at: float = 0.0
    gain_db: float = 0.0
    subtitle: str | None = None  # None = sin subtítulo automático
    subtitle_style: str = "label"
    subtitle_look: str = "sticker"


@dataclass(frozen=True)
class Music:
    mood: str = "cheerful"
    bpm: float | None = None
    seed: int = 0
    gain_db: float = -3.0


@dataclass(frozen=True)
class Edl:
    out_dir: Path
    segments: tuple[Segment, ...]
    texts: tuple[Text, ...] = ()
    sfx: tuple[Sfx, ...] = ()
    lines: tuple[Line, ...] = ()
    music: Music | None = None
    duck_db: float = -10.0  # cuánto baja la música mientras habla un gato
    text_sfx: dict = field(default_factory=lambda: dict(DEFAULT_TEXT_SFX))
    snap_to_beats: bool = True
    original_audio_db: float = 0.0
    color: dict = field(default_factory=dict)
    width: int = 1080
    height: int = 1920
    fps: int = 30
    main: str = "01.mp4"
    clean: str | None = "01_sin_musica.mp4"


def _resolve(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def load(path: Path, root: Path, durations: dict[Path, float] | None = None) -> Edl:
    raw = json.loads(path.read_text())
    if not raw.get("segments"):
        raise ValueError("el EDL no tiene segments")
    segments = tuple(
        Segment(**{**s, "src": _resolve(root, s["src"])}) for s in raw["segments"]
    )
    for i, seg in enumerate(segments):
        if not seg.src.exists():
            raise ValueError(f"segment {i}: no existe {seg.src}")
        if not 0 <= seg.start < seg.end:
            raise ValueError(f"segment {i}: start/end inválidos ({seg.start}, {seg.end})")
        if durations and seg.end > durations[seg.src] + 0.05:
            raise ValueError(f"segment {i}: end {seg.end} > duración {durations[seg.src]:.2f}")
        if not MIN_SPEED <= seg.speed <= MAX_SPEED:
            raise ValueError(f"segment {i}: speed fuera de [{MIN_SPEED}, {MAX_SPEED}]")
    texts = tuple(Text(**t) for t in raw.get("texts", []))
    sfx = tuple(Sfx(**s) for s in raw.get("sfx", []))
    lines = tuple(Line(**ln) for ln in raw.get("lines", []))
    for item in (*texts, *sfx, *lines):
        if not 0 <= item.segment < len(segments):
            raise ValueError(f"'{getattr(item, 'text', getattr(item, 'name', ''))}': "
                             f"segment {item.segment} no existe")
    outputs = raw.get("outputs", {})
    return Edl(
        out_dir=_resolve(root, raw["out_dir"]),
        segments=segments,
        texts=texts,
        sfx=sfx,
        lines=lines,
        music=Music(**raw["music"]) if raw.get("music") else None,
        duck_db=raw.get("duck_db", -10.0),
        text_sfx={**DEFAULT_TEXT_SFX, **raw.get("text_sfx", {})},
        snap_to_beats=raw.get("snap_to_beats", True),
        original_audio_db=raw.get("original_audio_db", 0.0),
        color=raw.get("color", {}),
        width=raw.get("width", 1080),
        height=raw.get("height", 1920),
        fps=raw.get("fps", 30),
        main=outputs.get("main", "01.mp4"),
        clean=outputs.get("clean", "01_sin_musica.mp4"),
    )


def resolve_text_sfx(edl: "Edl", rotation: tuple[str, ...]) -> list[str | None]:
    """Sonido de cada cartel, en el orden de edl.texts. Los "@cartel" rotan por orden de
    aparición y nunca repiten el sonido del cartel anterior."""
    by_time = sorted(range(len(edl.texts)),
                     key=lambda i: (edl.texts[i].segment, edl.texts[i].at))
    names: list[str | None] = [None] * len(edl.texts)
    previous, turn = None, 0
    for i in by_time:
        text = edl.texts[i]
        name = edl.text_sfx.get(text.style) if text.sfx == "auto" else text.sfx
        if name == ROTATE:
            name = rotation[turn % len(rotation)]
            turn += 1
            if name == previous and len(rotation) > 1:
                name = rotation[turn % len(rotation)]
                turn += 1
        names[i] = name
        previous = name or previous
    return names


def fit_voice_segments(segments: tuple[Segment, ...], lines: tuple["Line", ...],
                       line_durs: list[float], durations: dict[Path, float]
                       ) -> tuple[tuple[Segment, ...], tuple["Line", ...]]:
    """Ajusta el tramo de cada narración para que la frase quepa con 0.3–0.6 s a cada lado:
    primero ralentiza (hasta MIN_FIT_SPEED) y, si no basta, alarga el final."""
    new_segments, new_lines = list(segments), []
    for line, dur in zip(lines, line_durs):
        at = min(max(line.at, VOICE_PAD_MIN_S), VOICE_PAD_MAX_S)
        new_lines.append(replace(line, at=at))
        seg = new_segments[line.segment]
        lo, hi = at + dur + VOICE_PAD_MIN_S, at + dur + VOICE_PAD_MAX_S
        target = at + dur + VOICE_PAD_AFTER_S
        if lo <= seg.out_dur <= hi:
            continue
        if seg.out_dur > hi:  # sobra: se recorta el final
            new_segments[line.segment] = replace(seg, end=round(seg.start + target * seg.speed, 4))
            continue
        speed = (seg.end - seg.start) / target
        if speed >= MIN_FIT_SPEED:
            new_segments[line.segment] = replace(seg, speed=round(min(seg.speed, speed), 4))
        else:
            end = min(seg.start + target * MIN_FIT_SPEED, durations[seg.src])
            new_segments[line.segment] = replace(seg, speed=MIN_FIT_SPEED, end=round(end, 4))
    return tuple(new_segments), tuple(new_lines)


PUNCH_MIN_S = 0.6  # un remate de una palabra se "lee" de un vistazo


def reading_time(text: str, style: str = "label") -> float:
    """Segundos mínimos para leer un cartel (y mirar al gato a la vez)."""
    if style == "punch":
        return PUNCH_MIN_S
    return 0.8 + 0.2 * len(text.split())


def snap_to_beats(segments: tuple[Segment, ...], bpm: float,
                  durations: dict[Path, float], keep: set[int] = frozenset()
                  ) -> tuple[Segment, ...]:
    """Ajusta cada tramo a un número entero de beats (mínimo 1) moviendo su final.
    Los de `keep` (tramos con voz, ya ajustados a la frase) no se tocan."""
    beat = 60.0 / bpm
    snapped = []
    for i, seg in enumerate(segments):
        if i in keep:
            snapped.append(seg)
            continue
        beats = max(1, round(seg.out_dur / beat))
        end = seg.start + beats * beat * seg.speed
        while end > durations[seg.src] + 1e-3 and beats > 1:
            beats -= 1
            end = seg.start + beats * beat * seg.speed
        snapped.append(replace(seg, end=round(min(end, durations[seg.src]), 4)))
    return tuple(snapped)


def segment_starts(segments: tuple[Segment, ...]) -> list[float]:
    starts, t = [], 0.0
    for seg in segments:
        starts.append(t)
        t += seg.out_dur
    return starts


def crop_filter(seg: Segment, width: int, height: int) -> str:
    """Recorte al formato de salida centrado en (cx, cy), con zoom opcional."""
    aspect = width / height
    z = max(1.0, seg.zoom)
    w = f"min(iw\\,ih*{aspect:.5f})/{z:.3f}"
    h = f"min(iw\\,ih*{aspect:.5f})/{aspect:.5f}/{z:.3f}"
    x = f"max(0\\,min(iw-ow\\,{seg.cx:.3f}*iw-ow/2))"
    y = f"max(0\\,min(ih-oh\\,{seg.cy:.3f}*ih-oh/2))"
    return f"crop=w='{w}':h='{h}':x='{x}':y='{y}'"
