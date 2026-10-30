"""Bucle principal: escucha el grupo de Telegram, hace el cuestionario de cada post y los
procesa de uno en uno."""
import html
import logging
import queue
import threading
import time
import urllib.error

from . import pipeline
from .collector import Collector, PendingPost, extract_media
from .config import ROOT, STATE_DIR, load_config
from .interaction import Interaction
from .jira import Jira
from .survey import Answers, SurveyStore, load_cat_names
from .telegram import Telegram, TelegramError

NETWORK_RETRY_S = 5
CATS_FILE = ROOT / "brand" / "gatos.md"

log = logging.getLogger("somollorcos")

Job = tuple[PendingPost, Answers]


def worker(jobs: "queue.Queue[Job]", tg: Telegram, jira: Jira, cfg) -> None:
    while True:
        post, answers = jobs.get()
        sender = cfg.people[post.sender_id]
        try:
            pipeline.process(post, sender, tg, jira, cfg, answers)
        except Exception as err:  # noqa: BLE001 — cualquier fallo se reporta al grupo
            log.exception("Fallo procesando post de %s", sender.name)
            tg.send_html(post.chat_id, f"⚠️ No he podido preparar este post: "
                         f"{html.escape(str(err))[:400]}", reply_to=post.first_message_id)
        finally:
            jobs.task_done()


def from_known_member(chat_id: int, sender: dict, cfg) -> bool:
    if cfg.telegram_chat_id is None:
        log.warning("Mensaje del chat %s de %s (%s). Pon TELEGRAM_CHAT_ID en .env",
                    chat_id, sender.get("id"), sender.get("first_name", "?"))
        return False
    if chat_id != cfg.telegram_chat_id:
        return False
    if sender.get("id") not in cfg.people:
        log.warning("Remitente desconocido %s (%s): añádelo a config/people.json",
                    sender.get("id"), sender.get("first_name", "?"))
        return False
    return True


def too_big(message: dict, tg: Telegram) -> bool:
    media = extract_media(message)
    if media and media.size > tg.max_download_bytes:
        limit_mb = tg.max_download_bytes // (1024 * 1024)
        tg.send_html(message["chat"]["id"], f"⚠️ Este archivo pasa de {limit_mb} MB y no "
                     "puedo bajarlo. Recórtalo o déjalo en Drive.",
                     reply_to=message["message_id"])
        return True
    return False


def handle_update(update: dict, tg: Telegram, cfg, collector: Collector,
                  ui: Interaction) -> None:
    if query := update.get("callback_query"):
        chat_id = (query.get("message") or {}).get("chat", {}).get("id")
        if from_known_member(chat_id, query["from"], cfg):
            ui.on_callback(query)
        return
    message = update.get("message")
    if not message or not from_known_member(message["chat"]["id"], message.get("from", {}), cfg):
        return
    if extract_media(message):
        if not too_big(message, tg) and (post := collector.add(message)):
            ui.start(post)
    else:
        ui.on_text(message)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config()
    tg = Telegram(cfg.telegram_token, cfg.telegram_api_base, cfg.telegram_files_dir)
    jira = Jira(cfg.jira_base_url, cfg.jira_email, cfg.jira_token,
                cfg.jira_project_key, cfg.jira_issue_type)
    jobs: "queue.Queue[Job]" = queue.Queue()
    threading.Thread(target=worker, args=(jobs, tg, jira, cfg), daemon=True).start()
    collector = Collector()
    ui = Interaction(tg, cfg, SurveyStore(STATE_DIR / "surveys.json"),
                     load_cat_names(CATS_FILE), lambda post, answers: jobs.put((post, answers)))

    log.info("Escuchando Telegram…")
    offset = None
    while True:
        try:
            updates = tg.get_updates(offset)
        except (urllib.error.URLError, TimeoutError, TelegramError) as err:
            log.warning("Telegram no responde (%s), reintento en %ss", err, NETWORK_RETRY_S)
            time.sleep(NETWORK_RETRY_S)
            continue
        for update in updates:
            offset = update["update_id"] + 1
            try:
                handle_update(update, tg, cfg, collector, ui)
            except (TelegramError, urllib.error.URLError) as err:
                log.warning("No he podido atender un mensaje: %s", err)
        for post in collector.flush_ready():
            ui.start(post)
        ui.expire_old()


if __name__ == "__main__":
    main()
