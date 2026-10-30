"""Carga .env y config/people.json. Falla pronto si falta algo imprescindible."""
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX_DIR = ROOT / "inbox"
STATE_DIR = ROOT / "state"
# Volumen montado por docker-compose.yml para el servidor local de la Bot API.
TELEGRAM_FILES_DIR = STATE_DIR / "telegram-bot-api"

REQUIRED_KEYS = (
    "TELEGRAM_BOT_TOKEN",
    "JIRA_BASE_URL",
    "JIRA_EMAIL",
    "JIRA_API_TOKEN",
    "JIRA_PROJECT_KEY",
    "DRIVE_OUT_DIR",
)


@dataclass(frozen=True)
class Person:
    telegram_id: int
    name: str
    jira_account_id: str


@dataclass(frozen=True)
class Config:
    telegram_token: str
    telegram_chat_id: int | None
    telegram_api_base: str | None  # None = api.telegram.org
    telegram_files_dir: Path | None  # solo con servidor local
    jira_base_url: str
    jira_email: str
    jira_token: str
    jira_project_key: str
    jira_issue_type: str
    drive_out_dir: Path
    people: dict[int, Person]


def _parse_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _load_people(path: Path) -> dict[int, Person]:
    raw = json.loads(path.read_text())
    return {
        int(tg_id): Person(int(tg_id), data["name"], data.get("jira_account_id", ""))
        for tg_id, data in raw.items()
    }


def load_config() -> Config:
    env_path = ROOT / ".env"
    people_path = ROOT / "config" / "people.json"
    if not env_path.exists():
        raise SystemExit("Falta .env (copia .env.example y rellénalo)")
    if not people_path.exists():
        raise SystemExit("Falta config/people.json (copia people.example.json)")

    env = _parse_env(env_path)
    missing = [k for k in REQUIRED_KEYS if not env.get(k)]
    if missing:
        raise SystemExit(f"Faltan variables en .env: {', '.join(missing)}")

    chat_id = env.get("TELEGRAM_CHAT_ID")
    api_base = env.get("TELEGRAM_API_BASE", "").rstrip("/") or None
    return Config(
        telegram_token=env["TELEGRAM_BOT_TOKEN"],
        telegram_chat_id=int(chat_id) if chat_id else None,
        telegram_api_base=api_base,
        telegram_files_dir=TELEGRAM_FILES_DIR if api_base else None,
        jira_base_url=env["JIRA_BASE_URL"].rstrip("/"),
        jira_email=env["JIRA_EMAIL"],
        jira_token=env["JIRA_API_TOKEN"],
        jira_project_key=env["JIRA_PROJECT_KEY"],
        jira_issue_type=env.get("JIRA_ISSUE_TYPE", "Task"),
        drive_out_dir=Path(env["DRIVE_OUT_DIR"]).expanduser(),
        people=_load_people(people_path),
    )
