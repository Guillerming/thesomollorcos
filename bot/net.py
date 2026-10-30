"""HTTP con verificación TLS que funciona también con el Python de python.org.

Ese Python no trae certificados raíz propios; añadimos los de macOS (/etc/ssl/cert.pem).
"""
import ssl
import urllib.request
from pathlib import Path

MACOS_CA_BUNDLE = Path("/etc/ssl/cert.pem")


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if MACOS_CA_BUNDLE.exists():
        ctx.load_verify_locations(cafile=str(MACOS_CA_BUNDLE))
    return ctx


SSL_CONTEXT = _ssl_context()


def urlopen(url_or_request, data: bytes | None = None, timeout: float = 30):
    return urllib.request.urlopen(url_or_request, data=data, timeout=timeout,
                                  context=SSL_CONTEXT)
