"""Maps are kept in one SQLite file (data/blockplan.db).

Each map has a revision number. A save must say which revision it was based
on, so two people editing the same map cannot silently overwrite each other.
"""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager

from . import config

TYPES = {"goal", "ability", "team", "info", "system", "tech"}
WHEN = {"now", "planned", "retiring"}
HEALTH = {"", "good", "watch", "bad"}
CURRENCIES = {"£", "€", "$"}


class Conflict(Exception):
    def __init__(self, current_rev: int):
        self.current_rev = current_rev


class NotFound(Exception):
    pass


@contextmanager
def _db():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init():
    with _db() as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute(
            """CREATE TABLE IF NOT EXISTS maps (
                 id TEXT PRIMARY KEY,
                 name TEXT NOT NULL,
                 data TEXT NOT NULL,
                 rev INTEGER NOT NULL DEFAULT 1,
                 created_at REAL NOT NULL,
                 updated_at REAL NOT NULL)"""
        )


def _num(v) -> int:
    try:
        return max(0, int(round(float(v))))
    except (TypeError, ValueError):
        return 0


def _str(v, limit: int) -> str:
    return str(v if v is not None else "")[:limit]


def clean(data: dict) -> dict:
    """Keep only the fields the app understands, with sensible limits."""
    if not isinstance(data, dict):
        raise ValueError("A map must be an object.")
    blocks_in = data.get("blocks") if isinstance(data.get("blocks"), list) else []
    links_in = data.get("links") if isinstance(data.get("links"), list) else []
    blocks, ids = [], set()
    for b in blocks_in[:2000]:
        if not isinstance(b, dict) or b.get("type") not in TYPES:
            continue
        bid = _str(b.get("id"), 40) or uuid.uuid4().hex[:8]
        if bid in ids:
            continue
        ids.add(bid)
        blocks.append({
            "id": bid,
            "type": b["type"],
            "name": _str(b.get("name") or "Untitled", 120),
            "desc": _str(b.get("desc"), 2000),
            "owner": _str(b.get("owner"), 120),
            "health": b.get("health") if b.get("health") in HEALTH else "",
            "when": b.get("when") if b.get("when") in WHEN else "now",
            "cost": _num(b.get("cost")),
            "oneOff": _num(b.get("oneOff")),
            "x": _num(b.get("x")),
            "y": _num(b.get("y")),
        })
    links, seen = [], set()
    for l in links_in[:5000]:
        if not isinstance(l, dict):
            continue
        f, t = _str(l.get("from"), 40), _str(l.get("to"), 40)
        if f not in ids or t not in ids or f == t or (f, t) in seen:
            continue
        seen.add((f, t))
        links.append({
            "id": _str(l.get("id"), 40) or uuid.uuid4().hex[:8],
            "from": f,
            "to": t,
            "label": _str(l.get("label") or "relates to", 60),
        })
    return {
        "name": _str(data.get("name") or "Untitled map", 120),
        "currency": data.get("currency") if data.get("currency") in CURRENCIES else "£",
        "example": bool(data.get("example")),
        "blocks": blocks,
        "links": links,
    }


def list_maps() -> list:
    with _db() as con:
        rows = con.execute("SELECT id, name, rev, updated_at, data FROM maps ORDER BY updated_at DESC").fetchall()
    out = []
    for r in rows:
        d = json.loads(r["data"])
        out.append({"id": r["id"], "name": r["name"], "rev": r["rev"], "updated_at": r["updated_at"],
                    "blocks": len(d.get("blocks", []))})
    return out


def get_map(map_id: str) -> dict:
    with _db() as con:
        r = con.execute("SELECT * FROM maps WHERE id=?", (map_id,)).fetchone()
    if not r:
        raise NotFound()
    return {"id": r["id"], "rev": r["rev"], "updated_at": r["updated_at"], "map": json.loads(r["data"])}


def create_map(data: dict) -> dict:
    m = clean(data)
    map_id, now = uuid.uuid4().hex[:12], time.time()
    with _db() as con:
        con.execute("INSERT INTO maps (id, name, data, rev, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                    (map_id, m["name"], json.dumps(m), 1, now, now))
    return {"id": map_id, "rev": 1, "map": m}


def update_map(map_id: str, data: dict, base_rev: int) -> dict:
    m = clean(data)
    now = time.time()
    with _db() as con:
        r = con.execute("SELECT rev FROM maps WHERE id=?", (map_id,)).fetchone()
        if not r:
            raise NotFound()
        if r["rev"] != base_rev:
            raise Conflict(r["rev"])
        new_rev = r["rev"] + 1
        con.execute("UPDATE maps SET name=?, data=?, rev=?, updated_at=? WHERE id=? AND rev=?",
                    (m["name"], json.dumps(m), new_rev, now, map_id, base_rev))
    return {"id": map_id, "rev": new_rev}


def delete_map(map_id: str):
    with _db() as con:
        cur = con.execute("DELETE FROM maps WHERE id=?", (map_id,))
        if cur.rowcount == 0:
            raise NotFound()
