"""Settings, read from the .env file next to the app (see .env.example)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


VERSION = "1.3.1"

HOST = os.getenv("HOST", "0.0.0.0")
PORT = _int("PORT", 8080)
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data")).resolve()
DB_PATH = DATA_DIR / "blockplan.db"

# Optional login. Set both to ask for a username and password.
AUTH_USER = os.getenv("AUTH_USER", "").strip()
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "").strip()

# AI helper.
#   auto   - try each service that is set up, in AI_ORDER
#   claude, azure, openai, local - use only that one
#   off    - no AI helper
AI_MODE = os.getenv("AI_MODE", "auto").strip().lower()
AI_ORDER = [x.strip().lower() for x in os.getenv("AI_ORDER", "claude,azure,openai,local").split(",") if x.strip()]

# Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
# Only needed if your key works across several workspaces. The ID starts wrkspc_.
ANTHROPIC_WORKSPACE_ID = os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5").strip()
CLAUDE_MAX_TOKENS = _int("CLAUDE_MAX_TOKENS", 6000)

# Azure OpenAI (Azure AI Foundry)
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip()

# OpenAI, or any service that accepts OpenAI-style requests
OPENAI_BASE_URL = (os.getenv("OPENAI_BASE_URL", "").strip() or "https://api.openai.com/v1").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "").strip()
OPENAI_NAME = os.getenv("OPENAI_NAME", "").strip()

# A model on this machine through Ollama
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b").strip()
AI_TIMEOUT = _int("AI_TIMEOUT", 180)

MAX_BODY_BYTES = 5 * 1024 * 1024


def _path(name: str, default: Path | None = None) -> Path | None:
    v = os.getenv(name, "").strip()
    if not v:
        return default
    p = Path(v).expanduser()
    return (p if p.is_absolute() else BASE_DIR / p).resolve()


# HTTPS
#   self-signed - use a certificate from the certs folder, or make one for testing (default)
#   auto        - use a certificate if one is in the certs folder, otherwise plain HTTP
#   on          - use HTTPS, and stop with an explanation if there's no certificate
#   off         - plain HTTP
HTTPS = os.getenv("HTTPS", "self-signed").strip().lower()
CERT_DIR = _path("CERT_DIR", BASE_DIR / "certs")
_c, _k, _x = _path("TLS_CERT"), _path("TLS_KEY"), _path("TLS_PFX")
TLS_CERT = str(_c) if _c else ""
TLS_KEY = str(_k) if _k else ""
TLS_KEY_PASSWORD = os.getenv("TLS_KEY_PASSWORD", "")
TLS_PFX = str(_x) if _x else ""
TLS_PFX_PASSWORD = os.getenv("TLS_PFX_PASSWORD", "")
HTTPS_HOSTNAMES = [h.strip() for h in os.getenv("HTTPS_HOSTNAMES", "").split(",") if h.strip()]
