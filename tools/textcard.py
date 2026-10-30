"""Rótulos como PNG transparentes a tamaño de cuadro completo (se superponen en 0,0).

El ffmpeg de Homebrew no trae drawtext/libass, así que el texto se dibuja con Pillow.
Las posiciones respetan las zonas seguras de Reels: arriba ~10% (cabecera), abajo ~22%
(usuario y caption) y la columna derecha de iconos.
"""
from dataclasses import dataclass, replace
from itertools import combinations

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"
X_CENTER = 0.46  # un poco a la izquierda: deja libre la columna de iconos
MAX_LINES = 3


@dataclass(frozen=True)
class Style:
    size: int  # px a 1080 de ancho
    y: float  # centro vertical del bloque (fracción de la altura)
    max_w: float  # ancho máximo (fracción del ancho)


STYLES = {
    "hook": Style(92, 0.20, 0.80),   # gancho del primer segundo
    "label": Style(72, 0.64, 0.78),  # comentario durante el vídeo
    "punch": Style(150, 0.42, 0.80),  # una palabra de remate ("bonk", "wat")
    "cover": Style(116, 0.42, 0.80),  # portada: dentro del recorte 3:4 de la cuadrícula
}
LOOKS = ("outline", "sticker", "yellow")


def _greedy_lines(words: list[str], font, max_px: float) -> int:
    lines, current = 0, ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.getlength(candidate) > max_px and current:
            lines += 1
            current = word
        else:
            current = candidate
    return lines + (1 if current else 0)


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_px: float) -> list[str]:
    """Mínimo de líneas posible y, con ese número, las más parejas (sin palabras huérfanas)."""
    words = text.split()
    n_lines = _greedy_lines(words, font, max_px)
    if n_lines <= 1 or len(words) > 14:
        return [" ".join(words)] if n_lines <= 1 else _greedy_wrap(words, font, max_px)
    best, best_width = None, float("inf")
    for breaks in combinations(range(1, len(words)), n_lines - 1):
        bounds = (0, *breaks, len(words))
        lines = [" ".join(words[a:b]) for a, b in zip(bounds, bounds[1:])]
        widest = max(font.getlength(line) for line in lines)
        if widest <= max_px and widest < best_width:
            best, best_width = lines, widest
    return best or _greedy_wrap(words, font, max_px)


def _greedy_wrap(words: list[str], font, max_px: float) -> list[str]:
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.getlength(candidate) <= max_px or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    return lines + ([current] if current else [])


def _fit(text: str, style: Style, width: int) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    size = int(style.size * width / 1080)
    while True:
        font = ImageFont.truetype(FONT_PATH, size)
        lines = _wrap(text, font, style.max_w * width)
        too_wide = any(font.getlength(line) > style.max_w * width for line in lines)
        if (len(lines) <= MAX_LINES and not too_wide) or size <= 36:
            return font, lines
        size = int(size * 0.9)


def _text_block(lines: list[str], font, look: str) -> Image.Image:
    spacing = int(font.size * 0.18)
    stroke = max(4, font.size // 9)
    widths = [font.getlength(line) for line in lines]
    line_h = font.size + spacing
    pad = stroke * 3 if look != "sticker" else int(font.size * 0.45)
    block_w = int(max(widths)) + 2 * pad
    block_h = line_h * len(lines) + 2 * pad
    block = Image.new("RGBA", (block_w, block_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(block)

    if look == "sticker":
        draw.rounded_rectangle((0, 0, block_w - 1, block_h - 1), radius=int(font.size * 0.4),
                               fill=(255, 255, 255, 245))
        fill, stroke_fill, stroke = (20, 20, 20, 255), None, 0
    elif look == "yellow":
        fill, stroke_fill = (255, 214, 10, 255), (0, 0, 0, 255)
    else:
        fill, stroke_fill = (255, 255, 255, 255), (0, 0, 0, 255)

    for i, line in enumerate(lines):
        x = (block_w - widths[i]) / 2
        y = pad + i * line_h
        draw.text((x, y), line, font=font, fill=fill, stroke_width=stroke,
                  stroke_fill=stroke_fill)
    return block.rotate(-3, expand=True, resample=Image.BICUBIC) if look == "sticker" else block


def render(text: str, style: str = "label", look: str = "outline",
           size: tuple[int, int] = (1080, 1920), y: float | None = None) -> Image.Image:
    """y opcional: centro vertical del bloque (fracción), para esquivar al gato."""
    if style not in STYLES:
        raise ValueError(f"style desconocido: {style} (usa {', '.join(STYLES)})")
    if look not in LOOKS:
        raise ValueError(f"look desconocido: {look} (usa {', '.join(LOOKS)})")
    width, height = size
    st = STYLES[style] if y is None else replace(STYLES[style], y=y)
    font, lines = _fit(text, st, width)
    block = _text_block(lines, font, look)

    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    x = int(X_CENTER * width - block.width / 2)
    y = int(st.y * height - block.height / 2)
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 110), (x + 6, y + 9), mask=block.split()[3])
    canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(7)))
    canvas.alpha_composite(block, (max(0, x), max(0, y)))
    return canvas
