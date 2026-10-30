"""Calendario simple: un post al día, en el primer día libre a partir de mañana."""
import json
from datetime import date, timedelta
from pathlib import Path


def _read_dates(path: Path) -> list[str]:
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("dates", [])


def reserve_next_date(path: Path, today: date | None = None) -> date:
    taken = set(_read_dates(path))
    day = (today or date.today()) + timedelta(days=1)
    while day.isoformat() in taken:
        day += timedelta(days=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"dates": sorted(taken | {day.isoformat()})}, indent=2))
    return day
