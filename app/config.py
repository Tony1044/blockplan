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


VERSION = "1.1.0"

HOST = os.getenv("HOST", "0.0.0.0")
PORT = _int("PORT", 8080)
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data")).resolve()
DB_PATH = DATA_DIR / "blockplan.db"

# Optional login. Set both to ask for a username and password.
AUTH_USER = os.getenv("AUTH_USER", "").strip()
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "").strip()

# AI helper.
#   auto   - Claude first, local model if Claude is not set up or fails
#   claude - Claude only
#   local  - local model only; map content never leaves this machine
#   off    - no AI helper
AI_MODE = os.getenv("AI_MODE", "auto").strip().lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
# Only needed if your key works across several workspaces. The ID starts wrkspc_.
ANTHROPIC_WORKSPACE_ID = os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5").strip()
CLAUDE_MAX_TOKENS = _int("CLAUDE_MAX_TOKENS", 6000)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b").strip()
AI_TIMEOUT = _int("AI_TIMEOUT", 180)

MAX_BODY_BYTES = 5 * 1024 * 1024
