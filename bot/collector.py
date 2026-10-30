"""Agrupa los mensajes de Telegram en posts.

Telegram entrega cada elemento de un álbum como un mensaje distinto con el mismo
media_group_id, así que esperamos un poco tras el último antes de cerrar el post.
"""
import time
from dataclasses import dataclass, field

ALBUM_SETTLE_S = 4.0


@dataclass(frozen=True)
class Media:
    file_id: str
    kind: str  # "photo" | "video"
    size: int


@dataclass
class PendingPost:
    chat_id: int
    sender_id: int
    first_message_id: int
    is_album: bool
    media: list[Media] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    last_seen: float = field(default_factory=time.monotonic)


def extract_media(message: dict) -> Media | None:
    if photos := message.get("photo"):
        best = max(photos, key=lambda p: p.get("file_size", 0))
        return Media(best["file_id"], "photo", best.get("file_size", 0))
    for key in ("video", "animation"):
        if video := message.get(key):
            return Media(video["file_id"], "video", video.get("file_size", 0))
    # Enviado "como archivo" (sin compresión de Telegram).
    if doc := message.get("document"):
        mime = doc.get("mime_type", "")
        if mime.startswith(("image/", "video/")):
            kind = "photo" if mime.startswith("image/") else "video"
            return Media(doc["file_id"], kind, doc.get("file_size", 0))
    return None


class Collector:
    def __init__(self):
        self._albums: dict[str, PendingPost] = {}

    def add(self, message: dict) -> PendingPost | None:
        """Devuelve el post si ya está completo (elemento suelto)."""
        media = extract_media(message)
        if media is None:
            return None
        text = message.get("caption", "")
        group_id = message.get("media_group_id")

        if group_id is None:
            return PendingPost(
                chat_id=message["chat"]["id"],
                sender_id=message["from"]["id"],
                first_message_id=message["message_id"],
                is_album=False,
                media=[media],
                texts=[text] if text else [],
            )

        post = self._albums.setdefault(group_id, PendingPost(
            chat_id=message["chat"]["id"],
            sender_id=message["from"]["id"],
            first_message_id=message["message_id"],
            is_album=True,
        ))
        post.media.append(media)
        if text:
            post.texts.append(text)
        post.last_seen = time.monotonic()
        return None

    def flush_ready(self) -> list[PendingPost]:
        now = time.monotonic()
        ready = [gid for gid, p in self._albums.items() if now - p.last_seen >= ALBUM_SETTLE_S]
        return [self._albums.pop(gid) for gid in ready]
