"""De un post recibido a tarea en Jira: descarga → edición con Claude → Jira → aviso."""
import html
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from . import drive, schedule
from .collector import PendingPost
from .config import INBOX_DIR, ROOT, STATE_DIR, Config, Person
from .jira import Jira
from .survey import Answers
from .telegram import Telegram

CLAUDE_TIMEOUT_S = 30 * 60
CLAUDE_TOOLS = [
    "Read", "Write", "Edit", "Glob", "Grep", "Skill",
    "Bash(.venv/bin/python:*)", "Bash(ffmpeg:*)", "Bash(ffprobe:*)", "Bash(exiftool:*)",
    "Bash(sips:*)", "Bash(mkdir:*)", "Bash(ls:*)", "Bash(cp:*)",
]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "anon"


def ingest(post: PendingPost, sender: Person, tg: Telegram,
           answers: Answers | None = None) -> Path:
    post_id = f"{datetime.now():%Y%m%d-%H%M%S}-{_slug(sender.name)}"
    post_dir = INBOX_DIR / post_id
    post_dir.mkdir(parents=True)
    files = []
    for i, media in enumerate(post.media, start=1):
        default_ext = ".jpg" if media.kind == "photo" else ".mp4"
        saved = tg.download(media.file_id, post_dir / f"{i:02d}{default_ext}")
        files.append(saved.name)
    meta = {
        "post_id": post_id,
        "kind": "album" if post.is_album else "single",
        "sender_id": sender.telegram_id,
        "sender": sender.name,
        # Lo que contestaron en el cuestionario (manda sobre lo que Claude deduzca).
        "requested_format": answers.format if answers else None,
        "cats": list(answers.cats) if answers else [],
        "text": answers.idea if answers else "\n".join(post.texts),
        "skipped_survey": answers.skipped if answers else True,
        "voice": answers.voice if answers else False,
        "files": files,
        "received_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    (post_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return post_dir


def run_claude(post_dir: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt = (
        f"Usa la skill editar-post con el material de inbox/{post_dir.name}/. "
        f"out_dir = {out_dir}"
    )
    cmd = [
        "claude", "-p", prompt,
        # Solo la config del proyecto: evita hooks/plugins globales en modo desatendido.
        "--setting-sources", "project,local",
        "--permission-mode", "acceptEdits",
        "--add-dir", str(out_dir),
        "--allowedTools", *CLAUDE_TOOLS,
    ]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                            timeout=CLAUDE_TIMEOUT_S)
    (post_dir / "claude.log").write_text(result.stdout + "\n--- stderr ---\n" + result.stderr)
    post_json = out_dir / "post.json"
    if result.returncode != 0 or not post_json.exists():
        tail = (result.stdout.strip() or result.stderr.strip())[-300:]
        raise RuntimeError(f"La edición no ha generado post.json: {tail}")
    return json.loads(post_json.read_text())


def build_description(post: dict, link: str | None, out_dir: Path, meta: dict) -> str:
    where = f"[Carpeta en Drive|{link}]" if link else f"{{{{{out_dir}}}}} (Drive aún sincronizando)"
    parts = [
        f"h3. Archivos\n{where}\n" + "\n".join(
            [f"* {f}" for f in post.get("files", [])]
            + [f"* {f} _(alternativa)_" for f in post.get("alt_files", [])]),
        f"h3. Texto\n{{noformat}}{post.get('caption', '')}\n\n"
        f"{' '.join(post.get('hashtags', []))}{{noformat}}",
        f"h3. Detalles\n* Formato: {post.get('format')}\n"
        f"* Hora sugerida: {post.get('suggested_time', '19:30')}\n"
        f"* Texto alternativo: {post.get('alt_text', '')}",
    ]
    if hint := post.get("music_hint"):
        parts[-1] += f"\n* Música: {hint}"
    if meta.get("text"):
        parts.append(f"h3. Idea original\n{meta['text']}")
    if meta.get("cats"):
        parts.append(f"h3. Gatos\n{', '.join(meta['cats'])}")
    if notes := post.get("notes"):
        parts.append(f"h3. Notas de edición\n{notes}")
    return "\n\n".join(parts)


def process(post: PendingPost, sender: Person, tg: Telegram, jira: Jira, cfg: Config,
            answers: Answers | None = None) -> None:
    post_dir = ingest(post, sender, tg, answers)
    meta = json.loads((post_dir / "meta.json").read_text())
    out_dir = cfg.drive_out_dir / post_dir.name

    result = run_claude(post_dir, out_dir)
    link = drive.folder_link(out_dir)
    due = schedule.reserve_next_date(STATE_DIR / "schedule.json")
    key = jira.create_task(
        summary=f"[{result.get('format', 'post')}] {result.get('title', post_dir.name)}",
        description=build_description(result, link, out_dir, meta),
        due=due,
        assignee_id=sender.jira_account_id,
        labels=["thesomollorcos", _slug(result.get("format", "post"))],
    )

    mention = f'<a href="tg://user?id={sender.telegram_id}">{html.escape(sender.name)}</a>'
    when = f"{due:%d/%m} a las {html.escape(result.get('suggested_time', '19:30'))}"
    msg = (
        f"✅ Listo: <a href=\"{jira.browse_url(key)}\">{key}</a> · "
        f"{html.escape(result.get('title', ''))}\n"
        f"{mention}, te toca publicarlo el {when}."
    )
    if link:
        msg += f"\n📁 <a href=\"{link}\">Archivos en Drive</a>"
    tg.send_html(post.chat_id, msg, reply_to=post.first_message_id)
