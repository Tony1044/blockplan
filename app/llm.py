"""AI routing. Blockplan can use any of these, in the order set by AI_ORDER:

  claude  - Claude, from Anthropic
  azure   - Azure OpenAI (Azure AI Foundry), for organisations on Microsoft
  openai  - OpenAI, or any service that accepts OpenAI-style requests: OpenRouter, Mistral,
            Google Gemini, Groq, LM Studio, vLLM and others
  local   - a model on this machine through Ollama

AI_MODE in .env picks one of them, or "auto" to try each that is set up, in order.
With AI_MODE=local nothing about your maps leaves this machine.
"""
import json
import re
import time
from urllib.parse import urlparse

import httpx

from . import config

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


class AIError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _openai_name() -> str:
    if config.OPENAI_NAME:
        return config.OPENAI_NAME
    host = (urlparse(config.OPENAI_BASE_URL).hostname or "").lower()
    known = {"api.openai.com": "OpenAI", "openrouter.ai": "OpenRouter", "api.mistral.ai": "Mistral",
             "generativelanguage.googleapis.com": "Google Gemini", "api.groq.com": "Groq",
             "api.deepseek.com": "DeepSeek", "api.x.ai": "xAI", "api.together.xyz": "Together AI"}
    if host in known:
        return known[host]
    if host in ("localhost", "127.0.0.1", "::1", "host.docker.internal"):
        return "an AI server on this machine"
    return host or "OpenAI-compatible service"


def configured(key: str) -> bool:
    if key == "claude":
        return bool(config.ANTHROPIC_API_KEY)
    if key == "azure":
        return bool(config.AZURE_OPENAI_ENDPOINT and config.AZURE_OPENAI_API_KEY and config.AZURE_OPENAI_DEPLOYMENT)
    if key == "openai":
        return bool(config.OPENAI_MODEL and (config.OPENAI_API_KEY or _is_local(config.OPENAI_BASE_URL)))
    return False


def _is_local(url: str) -> bool:
    return (urlparse(url).hostname or "") in ("localhost", "127.0.0.1", "::1", "host.docker.internal")


def order() -> list:
    if config.AI_MODE == "off":
        return []
    if config.AI_MODE in ("claude", "azure", "openai", "local"):
        return [config.AI_MODE]
    seen, out = set(), []
    for k in config.AI_ORDER:
        if k in ("claude", "azure", "openai", "local") and k not in seen:
            seen.add(k); out.append(k)
    return out


_local_cache = {"at": 0.0, "ok": False}


async def local_ready() -> bool:
    """Is Ollama running with the chosen model? Checked at most every 30 seconds."""
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


async def ready(key: str) -> bool:
    return await local_ready() if key == "local" else configured(key)


def describe(key: str) -> dict:
    return {
        "claude": {"key": "claude", "name": "Claude", "model": config.CLAUDE_MODEL},
        "azure": {"key": "azure", "name": "Azure OpenAI", "model": config.AZURE_OPENAI_DEPLOYMENT},
        "openai": {"key": "openai", "name": _openai_name(), "model": config.OPENAI_MODEL},
        "local": {"key": "local", "name": "a model on this machine", "model": config.OLLAMA_MODEL},
    }[key]


async def status() -> dict:
    providers = []
    for k in order():
        d = describe(k); d["on"] = await ready(k); providers.append(d)
    on = [p for p in providers if p["on"]]
    if config.AI_MODE == "off":
        why = "The AI helper is turned off (AI_MODE=off)."
    elif not on:
        why = ("The AI helper isn't set up. Add a key for Claude, Azure OpenAI, or another AI service to the .env file, "
               f"or run a local model with Ollama ({config.OLLAMA_MODEL}), then restart Blockplan.")
    else:
        why = ""
    return {
        "available": bool(on), "mode": config.AI_MODE, "providers": providers, "message": why,
        # kept for older pages
        "claude": {"on": any(p["key"] == "claude" for p in on), "model": config.CLAUDE_MODEL},
        "local": {"on": any(p["key"] == "local" for p in on), "model": config.OLLAMA_MODEL},
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


def _error_text(r: httpx.Response) -> str:
    try:
        e = r.json().get("error", {})
        return (e.get("message") if isinstance(e, dict) else str(e)) or ""
    except ValueError:
        return ""


async def _post(name: str, url: str, body: dict, headers: dict) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=config.AI_TIMEOUT) as c:
            return await c.post(url, json=body, headers=headers)
    except httpx.TimeoutException:
        raise AIError("timeout", f"{name} took too long to answer. Try asking for less at a time.")
    except httpx.HTTPError:
        raise AIError("unreachable", f"Couldn't reach {name}. Check this machine's network connection and the address in .env.")


async def _claude(system: str, user: str) -> str:
    body = {"model": config.CLAUDE_MODEL, "max_tokens": config.CLAUDE_MAX_TOKENS,
            "system": system, "messages": [{"role": "user", "content": user}]}
    headers = {"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    if config.ANTHROPIC_WORKSPACE_ID:
        headers["anthropic-workspace-id"] = config.ANTHROPIC_WORKSPACE_ID
    r = await _post("Claude", ANTHROPIC_URL, body, headers)
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
        raise AIError("claude_error", f"Claude returned an error ({r.status_code}). {_error_text(r)}".strip())
    data = r.json()
    return "".join(p.get("text", "") for p in data.get("content", []) if p.get("type") == "text")


async def _chat_completions(name: str, url: str, headers: dict, model: str, setting: str, system: str, user: str) -> str:
    """OpenAI-style chat completions, used by OpenAI, Azure OpenAI and many other services."""
    body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"}}
    r = await _post(name, url, body, headers)
    if r.status_code == 400 and ("response_format" in r.text or "json_object" in r.text):
        body.pop("response_format")  # not every service supports it; the reply is still parsed tolerantly
        r = await _post(name, url, body, headers)
    if r.status_code in (401, 403):
        raise AIError("bad_key", f"{name} rejected the API key. Check the key in the .env file.")
    if r.status_code == 404:
        raise AIError("not_found", f"{name} couldn't find the model \"{model}\". Check {setting} and the address in .env.")
    if r.status_code == 429:
        raise AIError("busy", f"{name} is busy or your usage limit has been reached. Try again in a minute.")
    if r.status_code >= 400:
        raise AIError("ai_error", f"{name} returned an error ({r.status_code}). {_error_text(r)}".strip())
    try:
        msg = r.json()["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise AIError("bad_reply", f"{name} sent back an answer Blockplan couldn't read.")
    content = msg.get("content") or ""
    if isinstance(content, list):  # some services return a list of parts
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content


async def _openai(system: str, user: str) -> str:
    headers = {"content-type": "application/json"}
    if config.OPENAI_API_KEY:
        headers["authorization"] = "Bearer " + config.OPENAI_API_KEY
    return await _chat_completions(_openai_name(), config.OPENAI_BASE_URL.rstrip("/") + "/chat/completions", headers,
                                   config.OPENAI_MODEL, "OPENAI_MODEL", system, user)


async def _azure(system: str, user: str) -> str:
    base = config.AZURE_OPENAI_ENDPOINT.rstrip("/")
    if not base.endswith("/openai/v1"):
        base += "/openai/v1"
    headers = {"content-type": "application/json", "api-key": config.AZURE_OPENAI_API_KEY}
    return await _chat_completions("Azure OpenAI", base + "/chat/completions", headers,
                                   config.AZURE_OPENAI_DEPLOYMENT, "AZURE_OPENAI_DEPLOYMENT", system, user)


async def _local(system: str, user: str) -> str:
    body = {"model": config.OLLAMA_MODEL, "stream": False, "format": "json",
            "options": {"temperature": 0.3, "num_ctx": 16384},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    r = await _post("The local model", config.OLLAMA_URL + "/api/chat", body, {})
    if r.status_code >= 400:
        raise AIError("local_error", f"The local model returned an error ({r.status_code}).")
    return r.json().get("message", {}).get("content", "")


CALL = {"claude": _claude, "azure": _azure, "openai": _openai, "local": _local}


async def ask(system: str, user: str) -> tuple[dict, str]:
    """Returns (parsed reply, which service answered). Tries each service that is set up, in order."""
    if config.AI_MODE == "off":
        raise AIError("off", "The AI helper is turned off.")
    first_error = None
    for key in order():
        if not await ready(key):
            continue
        for attempt in (0, 1):
            try:
                prompt = user if attempt == 0 else user + "\n\nReply with the JSON object only."
                return parse_json(await CALL[key](system, prompt)), key
            except AIError as e:
                if e.code == "bad_reply" and attempt == 0:
                    continue  # one quiet retry with a firmer reminder
                first_error = first_error or e
                break
    raise first_error or AIError("not_set_up", "The AI helper isn't set up. See the README to add an AI service or a local model.")
