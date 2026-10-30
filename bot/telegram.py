"""Cliente mínimo de la Bot API de Telegram (solo stdlib).

Funciona contra api.telegram.org o contra el servidor local de docker-compose.yml.
En modo local, getFile devuelve una ruta absoluta dentro del contenedor y el archivo
ya está en el volumen montado, así que se copia del disco en vez de descargarlo.
"""
import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

from . import net

CLOUD_API_BASE = "https://api.telegram.org"
CLOUD_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
LOCAL_MAX_DOWNLOAD_BYTES = 2000 * 1024 * 1024
CONTAINER_DATA_DIR = PurePosixPath("/var/lib/telegram-bot-api")
POLL_TIMEOUT_S = 2
DEFAULT_CALL_TIMEOUT_S = POLL_TIMEOUT_S + 30
# Con servidor local, getFile no responde hasta tener el archivo entero.
GET_FILE_TIMEOUT_S = 15 * 60


class TelegramError(RuntimeError):
    pass


def host_path(container_path: str, files_dir: Path) -> Path:
    """Traduce una ruta del contenedor a la del volumen montado en el Mac."""
    relative = PurePosixPath(container_path).relative_to(CONTAINER_DATA_DIR)
    return files_dir.joinpath(*relative.parts)


class Telegram:
    def __init__(self, token: str, api_base: str | None = None,
                 local_files_dir: Path | None = None):
        self._token = token
        self._base = api_base or CLOUD_API_BASE
        self._local_files_dir = local_files_dir

    @property
    def max_download_bytes(self) -> int:
        return LOCAL_MAX_DOWNLOAD_BYTES if self._local_files_dir else CLOUD_MAX_DOWNLOAD_BYTES

    # http_timeout y no "timeout": getUpdates necesita mandar su propio parámetro timeout.
    def _call(self, method: str, http_timeout: float = DEFAULT_CALL_TIMEOUT_S,
              **params) -> dict | list:
        data = urllib.parse.urlencode(
            {k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in params.items()}
        ).encode()
        url = f"{self._base}/bot{self._token}/{method}"
        with net.urlopen(url, data=data, timeout=http_timeout) as resp:
            body = json.loads(resp.read())
        if not body.get("ok"):
            raise TelegramError(f"{method}: {body.get('description')}")
        return body["result"]

    def _call_checked(self, method: str, **params) -> dict | list:
        """Como _call, pero los 4xx de Telegram llegan como TelegramError con su motivo."""
        try:
            return self._call(method, **params)
        except urllib.error.HTTPError as err:
            try:
                description = json.loads(err.read()).get("description", str(err))
            except ValueError:
                description = str(err)
            raise TelegramError(f"{method}: {description}") from err

    def log_out(self) -> None:
        self._call("logOut")

    def get_updates(self, offset: int | None) -> list[dict]:
        params = {"timeout": POLL_TIMEOUT_S, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            params["offset"] = offset
        return self._call("getUpdates", **params)

    def send_html(self, chat_id: int, html: str, reply_to: int | None = None,
                  keyboard: list[list[dict]] | None = None) -> dict:
        params = {"chat_id": chat_id, "text": html, "parse_mode": "HTML",
                  "disable_web_page_preview": True}
        if reply_to:
            params["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
        if keyboard:
            params["reply_markup"] = {"inline_keyboard": keyboard}
        return self._call_checked("sendMessage", **params)

    def edit_html(self, chat_id: int, message_id: int, html: str,
                  keyboard: list[list[dict]] | None = None) -> None:
        params = {"chat_id": chat_id, "message_id": message_id, "text": html,
                  "parse_mode": "HTML", "disable_web_page_preview": True,
                  "reply_markup": {"inline_keyboard": keyboard or []}}
        self._call_checked("editMessageText", **params)

    def answer_callback(self, query_id: str, text: str | None = None, alert: bool = False) -> None:
        params = {"callback_query_id": query_id, "show_alert": alert}
        if text:
            params["text"] = text
        self._call_checked("answerCallbackQuery", **params)

    def download(self, file_id: str, dest: Path) -> Path:
        info = self._call("getFile", http_timeout=GET_FILE_TIMEOUT_S, file_id=file_id)
        file_path = info["file_path"]
        suffix = PurePosixPath(file_path).suffix or dest.suffix
        target = dest.with_suffix(suffix.lower())

        if self._local_files_dir and file_path.startswith("/"):
            source = host_path(file_path, self._local_files_dir)
            shutil.copyfile(source, target)
            source.unlink()  # la copia buena queda en inbox/
            return target

        url = f"{self._base}/file/bot{self._token}/{file_path}"
        with net.urlopen(url, timeout=GET_FILE_TIMEOUT_S) as resp, \
                open(target, "wb") as out:
            while chunk := resp.read(1 << 20):
                out.write(chunk)
        return target
