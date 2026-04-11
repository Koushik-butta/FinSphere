"""
keepalive.py — Background keep-alive pinger for Render free/starter tier.

Render's free tier will spin down your service after ~15 minutes of
inactivity, causing cold-start sleep. This module pings the app's own
/health endpoint every 14 minutes from a daemon thread so the service
is ALWAYS alive.

Usage: imported by app.py at startup.
"""

import threading
import time
import os
import logging

logger = logging.getLogger(__name__)

_PING_INTERVAL = 14 * 60       # 14 minutes (Render sleeps at 15 min idle)
_STARTED = False


def _ping_loop(app_url: str) -> None:
    """Infinite loop that GET-pings the /health endpoint."""
    # Wait a bit first so the server is fully ready
    time.sleep(30)
    while True:
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{app_url}/health",
                headers={"User-Agent": "FinSphere-KeepAlive/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.status
                logger.info(f"[KeepAlive] Pinged /health → HTTP {status}")
        except Exception as exc:
            logger.warning(f"[KeepAlive] Ping failed: {exc}")
        time.sleep(_PING_INTERVAL)


def start_keepalive() -> None:
    """
    Start the keep-alive daemon thread. Safe to call multiple times —
    only one thread will ever start.

    The RENDER_EXTERNAL_URL env var is automatically set by Render to your
    service's public URL (e.g. https://finsphere.onrender.com).
    Falls back to KEEP_ALIVE_URL if you want to override.
    """
    global _STARTED
    if _STARTED:
        return

    app_url = (
        os.environ.get("KEEP_ALIVE_URL") or
        os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    )

    if not app_url:
        logger.info(
            "[KeepAlive] No RENDER_EXTERNAL_URL found — "
            "keep-alive disabled (running locally or not on Render)."
        )
        return

    _STARTED = True
    t = threading.Thread(target=_ping_loop, args=(app_url,), daemon=True)
    t.name = "KeepAlive"
    t.start()
    logger.info(f"[KeepAlive] Started — pinging {app_url}/health every 14 min")
