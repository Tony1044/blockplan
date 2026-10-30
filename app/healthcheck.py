"""Used by Docker to check Blockplan is running, over HTTPS or HTTP."""
import ssl
import sys
import urllib.request

from . import config

for scheme in ("https", "http"):
    try:
        ctx = ssl._create_unverified_context() if scheme == "https" else None
        urllib.request.urlopen(f"{scheme}://127.0.0.1:{config.PORT}/healthz", timeout=3, context=ctx)
        sys.exit(0)
    except Exception:
        continue
sys.exit(1)
