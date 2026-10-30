# @thesomollorcos

Cuenta de Instagram sobre nuestros gatos: paseos y aventuras con ellos, siestas, comidas,
el día a día. También los gatos de la calle de los que cuidamos.

## Flujo (tres segmentos)

1. **Material de partida (compartido)**: Guille y su novia envían fotos/vídeos a un grupo de
   Telegram. El bot (`bot/`) los descarga a `inbox/<post_id>/` con un `meta.json`.
   - Un elemento suelto → post individual (reel si es vídeo, foto si es imagen).
   - Un álbum (varios a la vez) → carrusel.
   - El texto que acompaña al envío es contexto/idea para el copy.
2. **Selección, edición y preparación (Claude)**: skill `editar-post`. Deja el producto final
   en la carpeta de Google Drive del post y escribe `post.json`.
3. **Plataformas (humanos)**: el bot crea la tarea en Jira asignada a quien envió el material,
   con enlace a Drive, copy, hashtags y fecha. Avisa en el grupo mencionando a esa persona.
   Ellos publican. Los datos de audiencia los dan cuando se les piden.

## Tono de marca

- **Lo público (caption, rótulos, portada) en inglés escrito por los gatos**: minúsculas,
  frases cortas, faltas con patrón ("i smel flower", "im hidimg"). Reglas y ejemplos en
  `brand/voz.md`. Lo interno (notas, Jira, mensajes al grupo) en castellano.
- Gatos de la calle: tono cariñoso y respetuoso; nunca ubicaciones exactas de las colonias.
- Quién es quién (aspecto para reconocerlos y personalidad): `brand/gatos.md`.

## Reglas

- Nunca publicar nada: el segmento 3 es humano.
- Nunca borrar material original de `inbox/`.
- No inventar datos (lugares, nombres) que no estén en el material o en `brand/`.

## Piezas

- `bot/` (solo stdlib): Telegram → cuestionario (formato, gatos, voz, idea) → `claude -p`
  con la skill `editar-post` → Drive → Jira → aviso en el grupo.
- `tools/` (en `.venv`, numpy + Pillow): análisis, render (EDL → vídeo), música y efectos
  sintetizados, rótulos, portada, fotos y voces.
- Skills (`.claude/skills/`): `editar-post` (orquesta), `montaje-reel`, `rotulos`,
  `musica-gatuna`, `voces-gatunas`. Las preferencias de la cuenta viven ahí y en `brand/`.
- `brand/`: `gatos.md` (quién es quién y familias), `voz.md` (voz escrita),
  `voces.json` (perfil de Voicebox de cada gato con voz).

## Servicios que tienen que estar en marcha

1. **Docker Desktop** con `docker compose up -d`: servidor local de la Bot API (2 GB).
2. **Bot** como LaunchAgent: `scripts/service.sh install | restart | status | logs`.
3. **Voicebox** (app local, http://127.0.0.1:17493) para las voces. Sin él, los reels
   salen sin voz y se avisa en las notas.

Primera vez: `.env`, `config/people.json`, `python3 -m venv .venv &&
.venv/bin/pip install -r requirements.txt` y `python3 -m bot.logout_cloud`.

Tests: `.venv/bin/python -m unittest discover tests`.
