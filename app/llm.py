"""AI routing: Claude first, a local model (Ollama) as the fallback.

AI_MODE in .env decides which are allowed. With AI_MODE=local nothing about
your maps is sent outside this machine.
"""
import json
import re
import time

import httpx

from . import config

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


class AIError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def claude_allowed() -> bool:
    return config.AI_MODE in ("auto", "claude") and bool(config.ANTHROPIC_API_KEY)


def local_allowed() -> bool:
    return config.AI_MODE in ("auto", "local")


_local_cache = {"at": 0.0, "ok": False}


async def local_ready() -> bool:
    """Is Ollama running with the chosen model? Checked at most every 30 seconds."""
    if not local_allowed():
        return False
    if time.time() - _local_cache["at"] < 30:
        return _local_cache["ok"]
    ok = False
    try:
        async with httpx.AsyncClient(timeout=2.5) as c:
            r = await c.get(config.OLLAMA_URL + "/api/tags")
            if r.status_code == 200:
                names = {m.get("name", "") for m in r.json().get("models", [])}
                want = config.OLLAMA_MODEL
                ok = want in names or (":" not in want and f"{want}:latest" in names)
    except (httpx.HTTPError, ValueError):
        ok = False
    _local_cache.update(at=time.time(), ok=ok)
    return ok


async def status() -> dict:
    local = await local_ready()
    claude = claude_allowed()
    if config.AI_MODE == "off":
        why = "The AI helper is turned off (AI_MODE=off)."
    elif not claude and not local:
        why = ("Add an ANTHROPIC_API_KEY to the .env file, or run a local model with Ollama "
               f"(model {config.OLLAMA_MODEL}), then restart Blockplan.")
    else:
        why = ""
    return {
        "available": claude or local,
        "mode": config.AI_MODE,
        "claude": {"on": claude, "model": config.CLAUDE_MODEL if claude else None},
        "local": {"on": local, "model": config.OLLAMA_MODEL if local else None},
        "message": why,
    }


def parse_json(text: str) -> dict:
    """Read a JSON object from a model reply, tolerating a code fence or a stray sentence."""
    text = (text or "").strip()
    candidates = [text]
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        candidates.append(fence.group(1).strip())
    if "{" in text and "}" in text:
        candidates.append(text[text.index("{"): text.rindex("}") + 1])
    for c in candidates:
        try:
            v = json.loads(c)
            if isinstance(v, dict):
                return v
        except ValueError:
            continue
    raise AIError("bad_reply", "The helper's answer came back in the wrong shape. Try again.")


async def _claude(system: str, user: str) -> str:
    body = {"model": config.CLAUDE_MODEL, "max_tokens": config.CLAUDE_MAX_TOKENS,
            "system": system, "messages": [{"role": "user", "content": user}]}
    headers = {"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
               "content-type": "application/json"}
    if config.ANTHROPIC_WORKSPACE_ID:
        headers["anthropic-workspace-id"] = config.ANTHROPIC_WORKSPACE_ID
    try:
        async with httpx.AsyncClient(timeout=config.AI_TIMEOUT) as c:
            r = await c.post(ANTHROPIC_URL, json=body, headers=headers)
    except httpx.TimeoutException:
        raise AIError("timeout", "Claude took too long to answer. Try asking for less at a time.")
    except httpx.HTTPError:
        raise AIError("unreachable", "Couldn't reach Claude. Check this machine's internet connection.")
    if r.status_code == 401:
        raise AIError("bad_key", "Claude rejected the API key. Check ANTHROPIC_API_KEY in the .env file.")
    if r.status_code in (400, 403) and "workspace" in r.text.lower():
        raise AIError("workspace", "Claude needs to know which workspace to use. Create a key for a single "
                      "workspace, or add ANTHROPIC_WORKSPACE_ID to the .env file.")
    if r.status_code == 403:
        raise AIError("forbidden", "Claude refused the key. Check it is active and has credit in the Claude Console.")
    if r.status_code == 429:
        raise AIError("busy", "Claude is busy or your usage limit has been reached. Try again in a minute.")
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", {}).get("message", "")
        except ValueError:
            msg = ""
        raise AIError("claude_error", f"Claude returned an error ({r.status_code}). {msg}".strip())
    data = r.json()
    return "".join(p.get("text", "") for p in data.get("content", []) if p.get("type") == "text")


async def _local(system: str, user: str) -> str:
    body = {"model": config.OLLAMA_MODEL, "stream": False, "format": "json",
            "options": {"temperature": 0.3, "num_ctx": 16384},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    try:
        async with httpx.AsyncClient(timeout=config.AI_TIMEOUT) as c:
            r = await c.post(config.OLLAMA_URL + "/api/chat", json=body)
    except httpx.TimeoutException:
        raise AIError("timeout", "The local model took too long to answer. Try asking for less at a time.")
    except httpx.HTTPError:
        raise AIError("unreachable", "Couldn't reach the local model. Is Ollama running?")
    if r.status_code >= 400:
        raise AIError("local_error", f"The local model returned an error ({r.status_code}).")
    return r.json().get("message", {}).get("content", "")


async def ask(system: str, user: str) -> tuple[dict, str]:
    """Returns (parsed reply, which model answered)."""
    if config.AI_MODE == "off":
        raise AIError("off", "The AI helper is turned off.")
    first_error = None
    if claude_allowed():
        try:
            return parse_json(await _claude(system, user)), "claude"
        except AIError as e:
            if e.code == "bad_reply":
                # One quiet retry with a firmer reminder before giving up.
                try:
                    return parse_json(await _claude(system, user + "\n\nReply with the JSON object only.")), "claude"
                except AIError as e2:
                    first_error = e2
            else:
                first_error = e
    if await local_ready():
        try:
            return parse_json(await _local(system, user)), "local"
        except AIError as e:
            raise first_error or e
    raise first_error or AIError("not_set_up", "The AI helper isn't set up. See the README to add a Claude API key or a local model.")
