"""Diálogo del cuestionario con Telegram: enviar, reaccionar a botones y textos, caducar."""
import logging
import time
from collections.abc import Callable
from dataclasses import replace

from . import survey as sv
from .collector import PendingPost
from .config import Config
from .telegram import Telegram, TelegramError

log = logging.getLogger("somollorcos")

Enqueue = Callable[[PendingPost, sv.Answers], None]


class Interaction:
    def __init__(self, tg: Telegram, cfg: Config, store: sv.SurveyStore,
                 cat_names: tuple[str, ...], enqueue: Enqueue):
        self._tg = tg
        self._cfg = cfg
        self._store = store
        self._cats = cat_names
        self._enqueue = enqueue

    def _name(self, survey: sv.Survey) -> str:
        return self._cfg.people[survey.post.sender_id].name

    def start(self, post: PendingPost) -> None:
        survey = sv.new_survey(post)
        text, keyboard = sv.render(survey, self._cats, self._name(survey))
        sent = self._tg.send_html(post.chat_id, text, reply_to=post.first_message_id,
                                  keyboard=keyboard)
        self._store.put(replace(survey, message_id=sent["message_id"]))

    def _refresh(self, survey: sv.Survey, note: str = "") -> None:
        text, keyboard = sv.render(survey, self._cats, self._name(survey), note)
        try:
            self._tg.edit_html(survey.post.chat_id, survey.message_id, text, keyboard)
        except TelegramError as err:
            if "not modified" not in str(err):
                raise
        if survey.done:
            self._store.pop(survey.sid)
            self._enqueue(survey.post, survey.answers())
        else:
            self._store.put(survey)

    def on_callback(self, query: dict) -> None:
        parsed = sv.parse_callback(query.get("data", ""))
        survey = self._store.get(parsed[0]) if parsed else None
        if survey is None:
            self._tg.answer_callback(query["id"], "Este cuestionario ya no está activo.")
            return
        if query["from"]["id"] != survey.post.sender_id:
            self._tg.answer_callback(query["id"], f"Esto lo responde {self._name(survey)} 😼",
                                     alert=True)
            return
        _, action, value = parsed
        updated = sv.apply(survey, action, value, self._cats)
        self._tg.answer_callback(query["id"])
        if updated != survey:
            self._refresh(updated)

    def on_text(self, message: dict) -> bool:
        """Captura la idea si alguien tiene una pregunta de idea abierta. True si la usa."""
        text = message.get("text", "")
        if not text or text.startswith("/"):
            return False
        sender_id = message["from"]["id"]
        reply_to = (message.get("reply_to_message") or {}).get("message_id")
        survey = self._store.by_message(reply_to) if reply_to else None
        if survey is None or survey.post.sender_id != sender_id or survey.step != "idea":
            survey = self._store.waiting_idea(sender_id)
        if survey is None:
            return False
        self._refresh(sv.set_idea(survey, text))
        return True

    def expire_old(self, now: float | None = None) -> None:
        for survey in self._store.expired(now or time.time()):
            log.info("Cuestionario %s caducado: sigo con lo que hay", survey.sid)
            self._refresh(sv.expire(survey),
                          note="⏳ Sin respuesta en un rato: sigo con lo que hay.")
