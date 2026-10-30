---
name: voces-gatunas
description: Hacer hablar a los gatos en un reel o story con su voz grabada (Voicebox) - traducir la idea o el diálogo en castellano a inglés de niño, escribir las frases, colocarlas en el EDL con su subtítulo gatuno y comprobar que encajan. La usa editar-post cuando meta.voice es true o la idea pide voz.
---

# Voces gatunas

Las voces son grabaciones nuestras haciendo de cada gato, clonadas en Voicebox (app local,
http://127.0.0.1:17493). Lo gracioso es que **suene a gato de verdad hablando**, no a
narrador de estudio: frases de niño pequeño, dichas con su voz.

## 1. ¿Quién puede hablar?

`.venv/bin/python -m tools.voice --list` → gatos con voz y si Voicebox los tiene.

- Solo hablan los gatos de `brand/voces.json` con estado `ok`. Los demás no hablan: lo que
  dirían va en rótulos (skill `rotulos`).
- Si sale "Voicebox no responde… ¿está abierta la app?": haz el reel **sin voz** (todo en
  rótulos) y avísalo en `notes`: "Voicebox estaba cerrado; abridlo y reenviad si queréis voz".
- Nunca uses la voz de un gato para otro.

## 2. De la idea en castellano al inglés de niño

La idea (`meta.text`) suele venir en castellano, a veces con el diálogo casi escrito
("que diga: ¿quieres saber cómo acabé así?"). Tradúcela **por sentido, no palabra por
palabra**, y dale ritmo: el remate, al final de la frase.

### Cómo habla (estilo "niño", el aprobado)

- Frases cortas: **3–10 palabras**. Una idea por frase.
- Vocabulario de un niño de 5 años. Si un niño no lo diría, no se dice.
- Bien escrito, con mayúsculas y puntuación normales (la puntuación marca las pausas).
  **Nada de ortografía gatuna en lo hablado**: eso es solo para los subtítulos.
- Puede tener **como mucho una construcción infantil** por frase, nunca caos:
  "in all the day", "very very tired", "so much hungry", "this is mine. Mine.",
  "I do not like it", "my human is so slow".
- Repetir una palabra al final funciona: "Every day. Every day."
- Formas completas mejor que contracciones: "I am", "do not" (suena más lento y gatuno).

### Palabras prohibidas (suenan a adulto o a narrador)

whole, entire, entirely, therefore, however, indeed, actually, basically, literally, quite,
rather, perhaps, extremely, utterly, apparently, unfortunately, approximately, ridiculous,
exhausted, delighted, magnificent, adorable, majestic, journey, adventure, moreover.

Cámbialas por lo que diría un niño: whole day → all day / in all the day; exhausted →
so tired / very very tired; magnificent → so pretty; journey → walk.

### Ejemplos

| Idea (castellano) | ✅ Así | ❌ Así no |
|---|---|---|
| ¿Quieres saber cómo acabé así? | You want to know why I am so sleepy? | Wanna know how I ended up like this? |
| Tengo que sacar a mi humano perezoso cada día | Because every day I have to walk my lazy human. Every day. | Because lazy human i walked. |
| Es el único momento del día para descansar | And this is my only nap in all the day. | And this is my only nap of the whole day. |
| Esa comida es mía | This food is mine. Mine. | I hereby claim this delicious meal. |

### Etiquetas (opcional)

Chatterbox entiende `[sigh]` y `[chuckle]`. Como mucho una por reel, donde pegue
(suspiro de cansancio, risita traviesa). Ej.: "[sigh] And this is my only nap in all the day."

## 3. Colocar las frases en el EDL

```json
"lines": [
  {"cat": "Alioli", "text": "You want to know why I am so sleepy?",
   "segment": 0, "at": 0.3, "subtitle": "u wan kno why im so sleepy?",
   "subtitle_style": "hook", "subtitle_look": "outline"},
  {"cat": "Alioli", "text": "Because every day I have to walk my lazy human. Every day.",
   "segment": 1, "at": 0.1, "subtitle": "evry day i hav to wak my lazy human"}
],
"duck_db": -10
```

- **Pregunta → pausa → respuesta.** Si una frase pregunta algo ("You want to know why…?"),
  la siguiente no entra hasta 2–3 s después de que acabe (ráfaga cuqui en medio,
  `montaje-reel`). Nunca dos frases pegadas.
- **2–4 frases por reel**, 1–2 por story. La voz no debe ocupar más de la mitad del vídeo:
  deja respirar a la música y a los efectos.
- `subtitle`: la misma frase en voz gatuna escrita (`brand/voz.md`), más corta si hace
  falta. Sale sola, sincronizada con la voz (por defecto `label` + `sticker`). La primera
  frase puede ser el gancho: `"subtitle_style": "hook", "subtitle_look": "outline"`.
  No pongas además un rótulo con el mismo texto.
- **Una narración = un tramo, con aire alrededor: 0.3–0.6 s antes y después** (regla de
  Guille). Una frase de 1 s va en un tramo de 1.6–2.2 s, sin cortes en medio.
  - `at` entre 0.3 y 0.6 (se corrige solo si te sales).
  - El render ajusta ese tramo a la frase: lo **ralentiza** (hasta 0.7×) o, si no basta,
    **alarga su final**. Ese tramo no se ajusta al beat.
  - Por eso elige para cada frase un clip **tranquilo y con material de sobra** tras su
    `end` (que alargarlo no meta un plano movido). Mide antes las frases largas:
    `.venv/bin/python -m tools.voice --cat Alioli --text "…" --out inbox/<post>/_analysis/l1.wav`
    y `ffprobe` (se guarda en caché: no se vuelve a generar al renderizar).
  - En `render_report.json`, cada frase trae `pad_before`, `pad_after` y `pad_ok`.
- Música con voz: `gain_db` -5 y `duck_db` -10 (baja sola mientras hablan).
- Sin `sfx` encima de la voz; los efectos, entre frases.

## 4. Comprobar

Tras `tools.render`, mira `lines` en `render_report.json`:
- `overruns_video: true` → la frase se corta al final: acórtala o alarga el último tramo.
- Que ninguna frase pise a otra.
En `notes`, copia las frases dichas (inglés) y quién las dice.
