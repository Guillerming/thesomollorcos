---
name: rotulos
description: Rótulos en el vídeo y portada en la voz gatuna de la cuenta - qué decir, cuándo, dónde y con qué estilo. La usa editar-post al rellenar texts del EDL y al generar la portada.
---

# Rótulos y portada

Lee antes `brand/voz.md`: los rótulos son el gato hablando (inglés gatuno, minúsculas).
Mucha gente ve los reels sin sonido: **los rótulos cuentan la historia**.

## Qué escribir

- **Gancho** (`style: hook`, tramo 0, `at` 0, 1.5–2.5 s): la promesa del vídeo en ≤ 7
  palabras. "me goim for wak wif my gang", "day 3 of hidimg from teh vet",
  "9/6 demtists recommen". Siempre hay gancho.
- **Comentarios** (`style: label`): en como mucho la mitad de los tramos (los demás, solo
  gato y música). El gato narra o reacciona a lo que
  se ve, ≤ 6 palabras: "my bodigard", "he do parkour", "wak is hard. i lay".
  Nunca describas lo obvio ("a cat walking"); añade la opinión del gato.
- **Remate** (`style: punch`, `look: yellow`): 1 palabra o 2 en el momento cumbre
  ("bonk", "wat", "plof", "hehe"), 0.6–1 s, con su `sfx`.
- **Final**: en el último tramo, un rótulo que cierre o pida repetir ("this one is teh boss",
  "again tomorow", "wak complet").
- **Cartel con retardo**: el tramo empieza limpio y el cartel entra a `at` 0.6–1.0 s (con
  su blip automático, ver abajo). Primero se mira al gato, luego se lee el chiste.
- **Tiempo de lectura**: `dur` ≥ 0.8 s + 0.2 s por palabra (4 palabras → 1.6 s), y que el
  tramo dé para ello. `render_report.json` marca `too_short_to_read: true` si no: alarga el
  tramo, acorta el texto o quítalo.
- **No todo lleva cartel**: como mucho la mitad de los tramos. Si dudas, quítalo.
- Varía las palabras deformadas: no repitas "wak" en todos los rótulos.

## Blip al aparecer

Cada cartel suena al entrar, como en la tele japonesa. Sin escribir nada en `sfx`:
`label` → rota entre los sonidos de cartel (`jp_pikon`, `jp_pon`, `jp_kiran`, `jp_puyon`),
nunca dos iguales seguidos; `punch` → `jp_don`; `hook` y subtítulos de voz, sin efecto.

**Mejor elígelo tú según lo que dice el cartel** (tabla en `musica-gatuna`): cansancio →
`jp_zun`, travesura → `jp_tehe`, guapo → `jp_kira`, salto → `jp_pyon`, fallo → `jp_hyuu`.
Que en un mismo reel no se repita el mismo sonido de cartel más de dos veces.

**Sonido de cartel solo con cartel**: nunca pongas un sonido tipo cartel en un tramo sin
cartel (el espectador espera una pegatina que no llega). Para cambiarlo en un cartel: `"sfx": "jp_kira"` (o cualquiera de `musica-gatuna`);
para quitarlo: `"sfx": null`. Volumen: `"sfx_gain_db"` (por defecto -14; deben acompañar,
no tapar: no lo subas de -10).

Si el reel lleva voz (`lines`, skill `voces-gatunas`), cada frase dicha trae su subtítulo
automático: no repitas ese texto en otro rótulo y deja los `label` para lo que no se dice.

## Estilos

| style | Dónde | Para |
|---|---|---|
| `hook` | Arriba (20%) | Gancho inicial |
| `label` | Abajo-centro (64%), sobre el pie de Instagram | Comentarios |
| `punch` | Centro (42%), grande | Una palabra de remate |

| look | Aspecto |
|---|---|
| `outline` | Blanco con contorno negro (por defecto) |
| `sticker` | Negro sobre pegatina blanca inclinada: para frases sueltas del gato, "notas" |
| `yellow` | Amarillo con contorno: remates (`punch`) |

Alterna `outline` y `sticker` para que no sea monótono, pero no más de dos looks por reel
aparte del `yellow` de los remates. No pongas emojis en los rótulos (no se dibujan).

## Portada

`.venv/bin/python -m tools.cover inbox/<post>/edl.json --segment N --at T --text "…"
--position top|middle|bottom --out <out_dir>/cover.jpg`

- Fotograma: la cara del gato bien visible y expresiva (o el momento más gracioso). Elige
  `segment`/`at` mirando las hojas de contactos y `render_report.json`.
- Texto: 2–5 palabras, el título del episodio ("wak wif teh gang", "im hidimg").
  Puede repetir el gancho o ser más corto.
- `--position`: donde **no** esté la cara del gato. Gato abajo → `top`; gato arriba →
  `bottom`; gato a un lado → `middle` solo si no lo tapa.
- Mira la portada (Read) antes de terminar. Si el texto toca al gato, cambia `--position`
  o el fotograma.
