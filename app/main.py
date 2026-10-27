"""Blockplan web server: serves the page, stores maps, and runs the AI helper."""
import base64
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, llm, prompts, storage

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Blockplan", version=config.VERSION, docs_url=None, redoc_url=None)
storage.init()


@app.middleware("http")
async def guard(request: Request, call_next):
    if request.url.path == "/healthz":
        return await call_next(request)
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > config.MAX_BODY_BYTES:
        return JSONResponse({"detail": "That map is too large to save."}, status_code=413)
    if config.AUTH_USER and config.AUTH_PASSWORD:
        ok = False
        header = request.headers.get("authorization", "")
        if header.lower().startswith("basic "):
            try:
                user, _, pw = base64.b64decode(header[6:]).decode("utf-8").partition(":")
                ok = secrets.compare_digest(user, config.AUTH_USER) and secrets.compare_digest(pw, config.AUTH_PASSWORD)
            except (ValueError, UnicodeDecodeError):
                ok = False
        if not ok:
            return JSONResponse({"detail": "Sign in needed."}, status_code=401,
                                headers={"WWW-Authenticate": 'Basic realm="Blockplan"'})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/healthz")
def healthz():
    return {"ok": True, "version": config.VERSION}


@app.get("/api/status")
async def status():
    return {"version": config.VERSION, "ai": await llm.status()}


@app.get("/api/maps")
def list_maps():
    return {"maps": storage.list_maps()}


@app.post("/api/maps")
async def create_map(request: Request):
    body = await _json(request)
    try:
        return storage.create_map(body.get("map", body))
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)


@app.get("/api/maps/{map_id}")
def get_map(map_id: str):
    try:
        return storage.get_map(map_id)
    except storage.NotFound:
        return JSONResponse({"detail": "That map no longer exists."}, status_code=404)


@app.put("/api/maps/{map_id}")
async def save_map(map_id: str, request: Request):
    body = await _json(request)
    try:
        return storage.update_map(map_id, body.get("map", {}), int(body.get("rev", 0)))
    except storage.NotFound:
        return JSONResponse({"detail": "That map no longer exists."}, status_code=404)
    except storage.Conflict as c:
        return JSONResponse({"detail": "Someone else saved this map since you opened it.", "rev": c.current_rev},
                            status_code=409)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)


@app.delete("/api/maps/{map_id}")
def delete_map(map_id: str):
    try:
        storage.delete_map(map_id)
    except storage.NotFound:
        return JSONResponse({"detail": "That map no longer exists."}, status_code=404)
    return {"ok": True}


@app.post("/api/ai")
async def ai(request: Request):
    body = await _json(request)
    req = str(body.get("request", "")).strip()
    if not req:
        return JSONResponse({"code": "empty", "detail": "Type a question or request first."}, status_code=400)
    try:
        m = storage.clean(body.get("map", {}))
    except ValueError as e:
        return JSONResponse({"code": "bad_map", "detail": str(e)}, status_code=400)
    user = prompts.build(m, req, body.get("selected"), body.get("history") or [])
    try:
        result, source = await llm.ask(prompts.RULES, user)
    except llm.AIError as e:
        return JSONResponse({"code": e.code, "detail": e.message}, status_code=502)
    reply = str(result.get("reply") or "Done.").replace("\u2014", "\u2013")  # em dash to en dash
    changes = result.get("changes") if isinstance(result.get("changes"), dict) else {}
    return {"reply": reply, "changes": changes, "source": source}


async def _json(request: Request) -> dict:
    try:
        v = await request.json()
        return v if isinstance(v, dict) else {}
    except ValueError:
        return {}


def run():
    import uvicorn
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    run()
