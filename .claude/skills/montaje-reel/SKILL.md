---
name: montaje-reel
description: Reglas de montaje para reels de gatos - elegir los mejores momentos, ritmo de cortes, encuadre y estructura gancho-desarrollo-remate. La usa editar-post al escribir los segments del EDL.
---

# Montaje de reels

El objetivo es que nadie pase el reel en el primer segundo y que lo vean entero (y otra vez).
Esta cuenta es **familiar y cuqui, con chistes escritos**: el espectador tiene que poder
**leer el cartel y mirar al gato a la vez**. Nada de picadito: mejor menos cortes y más
largos que muchos y rápidos. Un vídeo casero de 37 s con 3 cortes no vale, pero uno de 17 s
con 10 cortes y un cartel en cada uno tampoco (feedback de Guille, 29/10/2026).

## 1. Mira antes de decidir

- Ejecuta `.venv/bin/python -m tools.analyze <vídeo>` por cada vídeo y **mira todas las hojas
  de contactos** (`sheet_NN.jpg`, Read). Cada miniatura lleva su segundo en amarillo.
- La tabla de `motion` (0–1) señala dónde pasa algo; `brightness` < 0.2 es demasiado oscuro;
  `loudness` > -30 LUFS indica sonido interesante (maullido, ronroneo, golpe).
- Para afinar un momento concreto, saca fotogramas sueltos:
  `ffmpeg -ss 16.2 -i src -frames:v 1 -vf scale=540:-2 inbox/<post>/_analysis/f_16_2.jpg`.
- Identifica a cada gato con `brand/gatos.md` (color, arnés). Si dudas, no lo nombres.

## 2. Encuentra la historia (antes de cortar)

Escribe en una frase qué pasa, en clave gatuna: "mayoneso sale de wak con su pandilla, se
cansa y se tira al suelo". Esa frase guía los cortes y los rótulos. Tipos que funcionan:
- **Aventura / misión**: salida → obstáculos → llegada ("day 1 of explorimg")
- **Antes / después** o **expectativa / realidad**
- **Personaje**: un gato haciendo lo suyo, contado por él ("im hidimg")
- **Remate cómico**: todo normal… y de pronto la tontería (tirarse al suelo, el salto fallido)

## 3. Estructura

1. **Gancho (0–1.5 s)**: el momento más llamativo o raro, aunque sea del final del vídeo.
   Nunca empieces con tiempo muerto, sombras o suelo. El rótulo `hook` va aquí.
2. **Desarrollo**: 4–10 tramos cortos que avanzan la historia, en orden lógico (no hace
   falta orden cronológico).
3. **Remate (último 1.5–3 s)**: la mejor reacción o el momento más tierno/gracioso, que pida
   volver a verlo. Ideal si el último plano enlaza con el primero (bucle).

## 4. Ritmo

- **Duración total**: 15–25 s por defecto (hasta 30 s con voz o mucha historia).
- **Tres tipos de tramo**, y se alternan:
  - **Ráfaga cuqui** (sin texto): 1–1.5 s, en grupos de 2–3 seguidos. Solo gato siendo gato
    (mirar a cámara, una pata, una cara). Dan respiro y tiempo para asimilar lo anterior.
  - **Tramo con chiste**: 2.5–4 s. Empieza limpio ~0.7 s, luego blip + cartel, y el cartel
    se queda al menos su tiempo de lectura (`rotulos`).
  - **Tramo con voz**: un solo clip por frase, con 0.3–0.6 s de aire antes y después
    (se ajusta solo al renderizar; ver `voces-gatunas`).
- **Como mucho la mitad de los tramos lleva cartel.** Los demás, solo música y gato.
- **Después de una pregunta o un gancho, pausa**: 2–3 s (una ráfaga cuqui de 2–3 clips) antes
  de la respuesta. Si la respuesta llega pegada, el espectador no ha asimilado la pregunta.
- Patrón que funciona: gancho/pregunta → ráfaga cuqui → respuesta en 1–2 tramos lentos con
  chiste → 1–2 tramos más (con o sin chiste) → cierre que enlaza con el principio.
- Con música, los tramos se ajustan solos a beats enteros (`snap_to_beats`): piensa en beats
  (a ~120 BPM, 2 beats = 1 s).
- **Velocidad**: `speed` 1.5–2.5 para trayectos aburridos pero necesarios (andar, llegar);
  0.5–0.7 para un salto, una caída o una cara graciosa. No abuses: 1–2 tramos por reel.
- Descarta sin piedad: planos movidos, a oscuras, solo suelo/sombras/pies, personas de cara
  sin necesidad, repeticiones del mismo momento.

## 5. Encuadre (por tramo)

- `cx`, `cy`: dónde está el gato **en el cuadro original** (0–1). El recorte se centra ahí.
- `zoom` 1.1–1.6 para acercarse al gato cuando sale pequeño (punch-in). Varía el zoom entre
  tramos seguidos para dar energía, pero no lo subas si la fuente es de baja resolución
  (< 720 px de ancho): se verá borroso; como máximo 1.3.
- Fuente horizontal → 9:16: elige bien `cx`, el gato tiene que quedar dentro.
- Deja aire para los rótulos: si el gato está arriba, el rótulo `label` (abajo) no lo tapa.

## 6. Audio original

- Si hay maullidos, ronroneos o sonidos graciosos: `original_audio_db` 0 a -3 y música más
  baja (`gain_db` -8 a -10). El sonido real del gato vale más que la música.
- Si es solo viento/ruido/voces: `original_audio_db` -30 (o -60 si molesta).

## 7. Antes de dar por bueno

Tras renderizar, haz una tira de fotogramas y mírala:
`ffmpeg -i <out>/01.mp4 -vf "fps=2,scale=216:384,tile=8x3" -frames:v 1 inbox/<post>/_analysis/check.jpg`
Comprueba: el gato está en cuadro en todos los tramos, ningún rótulo tapa la cara del gato,
nada está a oscuras, el gancho se entiende sin sonido. Si algo falla, corrige el EDL y
vuelve a renderizar.
