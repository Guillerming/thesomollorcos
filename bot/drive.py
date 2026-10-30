"""Enlaces web a carpetas sincronizadas por Google Drive para escritorio."""
import subprocess
import time
from pathlib import Path

DRIVE_ID_XATTR = "com.google.drivefs.item-id#S"
SYNC_WAIT_S = 120
SYNC_POLL_S = 3


def folder_link(folder: Path, wait_s: int = SYNC_WAIT_S) -> str | None:
    """Espera a que Drive asigne id a la carpeta y devuelve su URL web."""
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["xattr", "-p", DRIVE_ID_XATTR, str(folder)],
            capture_output=True, text=True,
        )
        item_id = result.stdout.strip()
        if result.returncode == 0 and item_id and not item_id.startswith("local-"):
            return f"https://drive.google.com/drive/folders/{item_id}"
        time.sleep(SYNC_POLL_S)
    return None
