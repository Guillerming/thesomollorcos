"""Desconecta el bot de api.telegram.org para poder usarlo con el servidor local.

Telegram lo exige una vez antes del primer arranque en local. Para volver al
servidor público hay que llamar a logOut en el local y esperar ~10 minutos.
"""
import logging

from .config import load_config
from .telegram import CLOUD_API_BASE, Telegram


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = load_config()
    Telegram(cfg.telegram_token, api_base=CLOUD_API_BASE).log_out()
    logging.info("Bot desconectado de api.telegram.org. Ya puedes usar el servidor local.")


if __name__ == "__main__":
    main()
