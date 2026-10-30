---
name: musica-gatuna
description: Cómo elegir y mezclar la música original sintetizada y los efectos de sonido de cada reel. La usa editar-post al rellenar music y sfx del EDL.
---

# Música y efectos

Toda la música se compone y sintetiza por código (`tools/music.py`): es nuestra, sin
derechos de terceros, y el tempo es exacto para cortar a ritmo. **Todo reel lleva música.**

## Mood

| mood | BPM | Cuándo |
|---|---|---|
| `cheerful` | 112–124 | Por defecto: paseos, juegos, día a día alegre |
| `silly` | 128–140 | Torpezas, caídas, tonterías, comida a lo bestia |
| `sneaky` | 96–108 | Acechar, esconderse, robar comida, travesuras |
| `sleepy` | 68–80 | Siestas, mimos, ronroneos, momentos tiernos |
| `epic` | 120–132 | "Misiones", saltos heroicos, exploración, el gato como héroe |

- `seed`: número cualquiera; cambia la melodía. Usa uno distinto en cada post
  (p. ej. los dígitos del post_id) para que no suenen todos igual.
- `bpm`: déjalo vacío salvo que quieras forzar un ritmo; se elige dentro del rango del mood.
- Puedes escuchar/medir una canción antes: `.venv/bin/python -m tools.music --mood silly
  --seconds 12 --seed 4 --out inbox/<post>/_analysis/m.wav`.

## Niveles (`gain_db` de music)

- Sin audio original útil: -3.
- Con audio original del gato que importa: -8 a -10, y `original_audio_db` 0.
- La mezcla final se normaliza a -14 LUFS (Instagram), no hace falta compensar.

## Efectos (`sfx`)

Remates cómicos sincronizados con la acción. Úsalos con intención: 1–4 por reel.

| name | Para |
|---|---|
| `boing` | Saltos, rebotes, tirarse al suelo |
| `bonk` | Golpes, chocar, caerse, "plof" |
| `pop` | Aparecer en cuadro, asomar la cabeza, un rótulo de remate |
| `whoosh` | Transición rápida, carrera, cambio de escena |
| `slide_up` / `slide_down` | Subir/bajar (trepar, caer despacio), expectación |
| `ding` | Idea, descubrimiento ("i smel flower") |
| `sparkle` | Momento bonito, gato guapo, "bitiful" |
| `tada` | Final triunfal, misión cumplida |

### Estilo tele japonesa (los preferidos de la cuenta)

| name | Para |
|---|---|
| `jp_pikon` | ピコン: aparece un cartel (de los que rotan en los `label`) |
| `jp_pon` | ポン: cartel tranquilo (rota) |
| `jp_kiran` | キラン: cartel con guiño (rota) |
| `jp_puyon` | ぷよん: cartel tonto y blandito (rota) |
| `jp_don` | ドン: el remate, la revelación (automático en los `punch`) |
| `jp_kira` | キラッ: gato guapo, momento bonito |
| `jp_pyon` | ぴょん: saltito |
| `jp_hyuu` | ヒューッ: caída, fallo, decepción |
| `jp_tehe` | てへ: travesura inocente, "hehe" |
| `jp_zun` | ズーン: bajón, cansancio, drama |
| `jp_chanchan` | ちゃんちゃん: "y fin", cierre cómico |
| `jp_shakin` | シャキーン: listo para la acción, momento heroico |

Los carteles ya traen su sonido (`rotulos`): no pongas otro efecto en el mismo instante.

**Efectos sueltos (`sfx`) solo para una acción visible del gato**: un salto, una caída,
un golpe, un bostezo. Nunca en ráfagas cuquis sin acción ni cuando aparece o desaparece un
subtítulo: suena a "aquí va una pegatina" y no la hay.

- `segment` + `at`: el efecto cae en el segundo `at` del tramo (salida). Ponlo en el
  fotograma exacto de la acción (míralo en la hoja de contactos).
- `gain_db`: -10 a -16 (los `jp_*`, -14 como en los carteles). Los efectos acompañan, no
  tapan la voz ni la música: a -6 o más suenan demasiado fuertes.

## Versión sin música

`render` exporta también `01_sin_musica.mp4` (audio original + efectos), por si al publicar
queréis usar un audio en tendencia de Instagram. Menciónalo en `notes` solo si el reel encaja
con alguna tendencia concreta.
