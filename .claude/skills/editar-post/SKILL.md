---
name: editar-post
description: Convierte el material de inbox/<post_id>/ en un post listo para publicar en Instagram (reel, foto o carrusel) con montaje, música original, efectos, rótulos y portada, y escribe post.json en la carpeta de salida.
---

# Editar post

Entrada: `inbox/<post_id>/meta.json` + los ficheros que lista. Salida: la carpeta `out_dir`
que indica el prompt (Google Drive). Todo lo público en la voz de `brand/voz.md`.

Herramientas (siempre con `.venv/bin/python -m tools.<x>` desde la raíz del proyecto):
`analyze` (mirar), `render` (EDL → vídeo con música, efectos y rótulos), `cover` (portada),
`photo` (fotos), `music` (escuchar una música suelta). Skills de apoyo, **léelas**:
`montaje-reel`, `musica-gatuna`, `rotulos`.

## 1. Entender

- Lee `meta.json`, `brand/gatos.md` y `brand/voz.md`. Del cuestionario de Telegram vienen
  (y **mandan** sobre lo que tú deduzcas):
  - `requested_format`: `reel` | `post` | `story` | `carousel` → el formato a entregar.
  - `cats`: los gatos que salen, según quien grabó. Úsalos para identificarlos y nómbralos
    con confianza; si ves uno más que no está en la lista, no lo nombres.
  - `text`: la idea del post. Si la hay, la historia y el gancho salen de ella.
  - `skipped_survey: true` → no contestaron; decide tú como siempre.
  - `voice: true` (o la idea pide que hablen / que digan algo) → los gatos hablan con su
    voz grabada: **lee la skill `voces-gatunas`** y añade `lines` al EDL.
- Vídeos: `tools.analyze` y mira **todas** las hojas de contactos.
  Fotos: míralas con Read (HEIC: `sips -s format jpeg x.heic --out inbox/<post>/_analysis/x.jpg`).
- Identifica a los gatos (arnés negro = Mayoneso, rojo = Alioli…) y escribe la historia en
  una frase (ver `montaje-reel` §2).

## 2. Formato

Si hay `requested_format`, ese manda. Si no encaja con el material (p. ej. `post` con un
solo vídeo), haz lo más parecido y explícalo en `notes`. Sin `requested_format`:

- `single` + vídeo → **reel** 9:16.
- `single` + foto → **foto** 4:5 con un rótulo `sticker` o `label` si aporta.
- **story** (solo si lo piden): vertical 9:16, para el día a día y lo espontáneo.
  - Vídeo: `tools.render` normal pero corto (5–15 s por story; varios vídeos → varias stories
    `01.mp4`, `02.mp4`…), rótulo `hook` o `sticker`, sin `clean`.
  - Foto: `tools.photo --aspect 9:16` con un rótulo `sticker`.
  - Deja libre el tercio inferior: ahí van los stickers interactivos de Instagram.
  - `caption` y `hashtags` vacíos; en `notes`, propón 1–2 stickers en voz gatuna
    (encuesta "fud or naps?", pregunta "ask mayoneso", cuenta atrás, mención).
  - `format: "story"` en `post.json`.
- `album` → **carrusel** (máx. 20): el elemento más potente primero; fotos con
  `tools.photo --aspect 4:5`; vídeos con `tools.render` con `"width": 1080, "height": 1350`
  y salida `NN.mp4`. Rótulo en el primero (gancho) y, si suma, en alguno más.
- `album` solo de vídeos y con historia → mejor **un reel** que los monte juntos (varios
  `src` en el mismo EDL). Dilo en `notes`.

## 3. Reel: escribir `inbox/<post_id>/edl.json`

```json
{
  "out_dir": "<out_dir>",
  "segments": [
    {"src": "inbox/<post_id>/01.mp4", "start": 16.2, "end": 17.8, "speed": 1.0,
     "cx": 0.45, "cy": 0.6, "zoom": 1.2}
  ],
  "texts": [
    {"text": "me goim for wak wif my gang", "segment": 0, "at": 0.0, "dur": 2.0,
     "style": "hook", "look": "outline"}
  ],
  "sfx": [{"name": "jp_pyon", "segment": 3, "at": 0.15, "gain_db": -14}],
  "music": {"mood": "cheerful", "seed": 184852, "gain_db": -3},
  "snap_to_beats": true,
  "original_audio_db": -30,
  "color": {"contrast": 1.05, "saturation": 1.12, "brightness": 0.0, "gamma": 1.0},
  "outputs": {"main": "01.mp4", "clean": "01_sin_musica.mp4"}
}
```

- Tiempos de `segments` en segundos del vídeo **original**. `texts`/`sfx` anclados a un tramo
  (`segment`) con `at` = segundos desde el inicio de ese tramo **en la salida**.
- Ajusta `color` si hace falta (sombras duras → `gamma` 1.1; foto lavada → `contrast` 1.1).
- Ejecuta `.venv/bin/python -m tools.render inbox/<post_id>/edl.json` y lee el informe.
- **Revisa** con la tira de fotogramas (`montaje-reel` §7). Corrige y vuelve a renderizar
  si algo falla. Máximo 3 iteraciones.
- Portada con `tools.cover` (ver `rotulos`) y mírala.

## 4. Copy (post.json)

- `caption`: 1–3 líneas en voz gatuna (`brand/voz.md`), la primera es el gancho. Puede
  ampliar el chiste del vídeo, no repetirlo palabra por palabra.
- `hashtags`: según `brand/voz.md`.
- `alt_text`: inglés correcto y descriptivo.
- `suggested_time`: "19:30" mientras no haya datos de audiencia.

## 5. Salida

Escribe `<out_dir>/post.json`:

```json
{
  "title": "Resumen corto en castellano para la tarea (máx 60 caracteres)",
  "format": "reel | foto | carrusel",
  "files": ["01.mp4", "cover.jpg"],
  "alt_files": ["01_sin_musica.mp4"],
  "caption": "me goim for wak wif my gang. they protec me 😼",
  "hashtags": ["#catsofinstagram", "…"],
  "alt_text": "A white cat on a leash walks down a cobbled street escorted by black cats.",
  "suggested_time": "19:30",
  "music_hint": "Música original incluida (cheerful, 124 BPM). Versión sin música en alt_files por si queréis un audio en tendencia.",
  "notes": "En castellano: historia elegida, tramos usados y descartados, qué gato es quién, dudas."
}
```

- En `out_dir` deja solo lo publicable (vídeos, fotos, portada, post.json). Lo de trabajo va
  a `inbox/<post_id>/_analysis/`.
- Si la fuente es de baja resolución (< 720 px de ancho), avísalo en `notes`: "enviad el
  vídeo como archivo en Telegram para que llegue sin comprimir".

Responde solo con `OK` al terminar, o `ERROR: <motivo>` si no se puede generar el post.
