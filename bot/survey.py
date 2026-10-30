"""Cuestionario por post (formato, gatos, idea), al estilo BotFather: un solo mensaje que se
va editando con botones. Aquí solo hay estado y presentación; el diálogo con Telegram está
en interaction.py.
"""
import html
import json
import re
import secrets
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from .collector import Media, PendingPost

FORMATS = {"reel": "🎞 Reel", "post": "🖼 Post", "story": "📱 Story", "carousel": "🗂 Carrusel"}
VOICE_FORMATS = {"reel", "story"}  # solo en vídeo tiene sentido que hablen
SURVEY_TIMEOUT_S = 3 * 3600
CATS_PER_ROW = 3
NO_IDEA_WORDS = {"no", "nada", "ninguna", "-", "sin idea"}
_TABLE_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|")
_NOT_A_NAME = {"nombre", "?", ""}


@dataclass(frozen=True)
class Answers:
    format: str
    cats: tuple[str, ...]
    idea: str
    skipped: bool = False
    voice: bool = False


@dataclass(frozen=True)
class Survey:
    sid: str
    post: PendingPost
    step: str = "format"  # format → cats → (voice) → idea → done
    format: str | None = None
    cats: tuple[str, ...] = ()
    idea: str = ""
    skipped: bool = False
    voice: bool = False
    message_id: int | None = None
    created: float = field(default_factory=time.time)

    @property
    def done(self) -> bool:
        return self.step == "done"

    def answers(self) -> Answers:
        return Answers(self.format or suggested_format(self.post), self.cats, self.idea,
                       self.skipped, self.voice)

    @property
    def asks_voice(self) -> bool:
        return self.format in VOICE_FORMATS


def load_cat_names(path: Path) -> tuple[str, ...]:
    """Primera columna de las tablas de brand/gatos.md, en orden (casa y luego calle)."""
    names = []
    for line in path.read_text().splitlines():
        match = _TABLE_ROW.match(line)
        if match and not set(match.group(1)) <= set("-: "):
            name = match.group(1)
            if name.lower() not in _NOT_A_NAME and name not in names:
                names.append(name)
    return tuple(names)


def suggested_format(post: PendingPost) -> str:
    if post.is_album:
        return "carousel"
    return "reel" if post.media[0].kind == "video" else "post"


def new_survey(post: PendingPost) -> Survey:
    return Survey(sid=secrets.token_hex(3), post=post, idea="\n".join(post.texts).strip())


def _to_idea(survey: Survey) -> Survey:
    # Si ya mandaron un texto con el material, esa es la idea: no se pregunta.
    return replace(survey, step="done" if survey.idea else "idea")


def _after_cats(survey: Survey) -> Survey:
    return replace(survey, step="voice") if survey.asks_voice else _to_idea(survey)


def apply(survey: Survey, action: str, value: str, cat_names: tuple[str, ...]) -> Survey:
    """Aplica la pulsación de un botón. Devuelve un Survey nuevo (o el mismo si no aplica)."""
    if action == "skip":
        return replace(survey, format=survey.format or suggested_format(survey.post),
                       step="done", skipped=True)
    if action == "back":
        previous = {"cats": "format", "voice": "cats",
                    "idea": "voice" if survey.asks_voice else "cats"}.get(survey.step)
        return replace(survey, step=previous) if previous else survey
    if survey.step == "voice" and action == "v" and value in ("0", "1"):
        return _to_idea(replace(survey, voice=value == "1"))
    if survey.step == "format" and action == "f" and value in FORMATS:
        return replace(survey, format=value, step="cats")
    if survey.step == "cats":
        if action == "c" and value.isdigit() and int(value) < len(cat_names):
            name = cat_names[int(value)]
            cats = tuple(c for c in survey.cats if c != name) if name in survey.cats \
                else (*survey.cats, name)
            return replace(survey, cats=cats)
        if action == "cn":
            return _after_cats(replace(survey, cats=()))
        if action == "cd":
            return _after_cats(survey)
    if survey.step == "idea" and action == "in":
        return replace(survey, idea="", step="done")
    return survey


def set_idea(survey: Survey, text: str) -> Survey:
    if survey.step != "idea":
        return survey
    idea = "" if text.strip().lower() in NO_IDEA_WORDS else text.strip()
    return replace(survey, idea=idea, step="done")


def expire(survey: Survey) -> Survey:
    return replace(apply(survey, "skip", "", ()), skipped=True)


def parse_callback(data: str) -> tuple[str, str, str] | None:
    parts = data.split(":")
    if len(parts) != 4 or parts[0] != "s":
        return None
    return parts[1], parts[2], parts[3]


def _button(survey: Survey, label: str, action: str, value: str = "") -> dict:
    return {"text": label, "callback_data": f"s:{survey.sid}:{action}:{value}"}


def _summary(survey: Survey) -> list[str]:
    lines = []
    if survey.format:
        lines.append(f"Formato: <b>{FORMATS[survey.format]}</b>")
    if survey.step in ("idea", "done") or survey.cats:
        lines.append(f"🐱 Gatos: <b>{html.escape(', '.join(survey.cats) or 'no indicado')}</b>")
    if survey.asks_voice and survey.step in ("idea", "done"):
        lines.append(f"🎙️ Voz: <b>{'sí, que hablen' if survey.voice else 'no'}</b>")
    if survey.step == "done":
        lines.append(f"💡 Idea: <b>{html.escape(survey.idea) if survey.idea else 'ninguna'}</b>")
    return lines


def render(survey: Survey, cat_names: tuple[str, ...], sender_name: str,
           note: str = "") -> tuple[str, list[list[dict]] | None]:
    """Texto HTML y teclado inline para el paso actual."""
    n = len(survey.post.media)
    header = f"<b>{html.escape(sender_name)}</b>, has mandado {n} archivo{'s' if n > 1 else ''}."
    lines = [header, *_summary(survey), ""]

    if survey.step == "format":
        suggested = suggested_format(survey.post)
        lines.append("🎬 ¿Qué quieres hacer con esto?")
        buttons = [_button(survey, f"{label}{' ⭐' if key == suggested else ''}", "f", key)
                   for key, label in FORMATS.items()]
        keyboard = [buttons[:2], buttons[2:], [_button(survey, "⏩ Hazlo tú", "skip")]]
    elif survey.step == "cats":
        lines.append("🐱 Marca los gatos que salen (toca para marcar o desmarcar):")
        cat_buttons = [_button(survey, f"{'✅ ' if name in survey.cats else ''}{name}", "c", str(i))
                       for i, name in enumerate(cat_names)]
        keyboard = [cat_buttons[i:i + CATS_PER_ROW]
                    for i in range(0, len(cat_buttons), CATS_PER_ROW)]
        keyboard.append([_button(survey, "↩️ Atrás", "back"),
                         _button(survey, "🤷 Ninguno / no sé", "cn"),
                         _button(survey, "➡️ Listo", "cd")])
    elif survey.step == "voice":
        lines.append("🎙️ ¿Que los gatos hablen? Con su voz grabada, en inglés. Si quieres que "
                     "digan algo concreto, escríbelo luego en la idea (en castellano vale).")
        keyboard = [[_button(survey, "🗣 Sí, que hablen", "v", "1"),
                     _button(survey, "🤐 No", "v", "0")],
                    [_button(survey, "↩️ Atrás", "back")]]
    elif survey.step == "idea":
        lines.append("💡 ¿Alguna idea para el post? <b>Escríbela en el grupo</b> (o responde a "
                     "este mensaje), o pulsa «Sin idea».")
        keyboard = [[_button(survey, "↩️ Atrás", "back"), _button(survey, "🙅 Sin idea", "in")]]
    else:
        lines.append(note or "⏳ Me pongo con ello…")
        keyboard = None
    return "\n".join(lines).strip(), keyboard


# --- Persistencia (sobrevive a reinicios del bot) -------------------------------------

def _to_dict(survey: Survey) -> dict:
    return asdict(survey)


def _from_dict(data: dict) -> Survey:
    post_data = data["post"]
    post = PendingPost(**{**post_data, "media": [Media(**m) for m in post_data["media"]]})
    return Survey(**{**data, "post": post, "cats": tuple(data["cats"])})


class SurveyStore:
    def __init__(self, path: Path):
        self._path = path
        self._items: dict[str, Survey] = {}
        if path.exists():
            self._items = {sid: _from_dict(d) for sid, d in json.loads(path.read_text()).items()}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({sid: _to_dict(s) for sid, s in self._items.items()},
                                         ensure_ascii=False, indent=1))

    def put(self, survey: Survey) -> None:
        self._items[survey.sid] = survey
        self._save()

    def get(self, sid: str) -> Survey | None:
        return self._items.get(sid)

    def pop(self, sid: str) -> None:
        if self._items.pop(sid, None):
            self._save()

    def by_message(self, message_id: int) -> Survey | None:
        return next((s for s in self._items.values() if s.message_id == message_id), None)

    def waiting_idea(self, sender_id: int) -> Survey | None:
        waiting = [s for s in self._items.values()
                   if s.step == "idea" and s.post.sender_id == sender_id]
        return max(waiting, key=lambda s: s.created, default=None)

    def expired(self, now: float) -> list[Survey]:
        return [s for s in self._items.values()
                if not s.done and now - s.created > SURVEY_TIMEOUT_S]
