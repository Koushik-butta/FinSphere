"""
gunicorn.conf.py — Production Gunicorn configuration for Render deployment.

Start command (in Render dashboard):
    gunicorn app:app -c gunicorn.conf.py
"""

import multiprocessing

# ── Worker settings ───────────────────────────────────────────────────────────
# 2 workers is optimal for Render's free/starter tier (512MB RAM).
# Avoid auto-calculating (2*cpu+1) — free tier has 1 vCPU so 3 workers OOMs.
workers     = 2
worker_class = "sync"        # sync is most stable; use "gthread" if needed
threads     = 2              # threads-per-worker for sync+thread hybrid

# ── Timeout & keepalive ───────────────────────────────────────────────────────
timeout       = 120          # 120s before killing a stuck worker (fixes 502s)
keepalive     = 5            # keep-alive seconds on idle connections
graceful_timeout = 30        # seconds to let a worker finish before SIGKILL

# ── Performance ───────────────────────────────────────────────────────────────
preload_app  = True          # load app code once in master, fork to workers
                             # saves RAM and catches startup errors early
max_requests       = 1000    # recycle workers after 1000 requests (prevents leaks)
max_requests_jitter = 50     # spread recycling to avoid all workers restarting at once

# ── Binding ───────────────────────────────────────────────────────────────────
bind = "0.0.0.0:10000"      # Render injects PORT env var; 10000 is the default

# ── Logging ───────────────────────────────────────────────────────────────────
accesslog  = "-"             # stdout (visible in Render logs)
errorlog   = "-"             # stderr
loglevel   = "info"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sµs'

# ── Hooks ─────────────────────────────────────────────────────────────────────
def on_starting(server):
    server.log.info("FinSphere Gunicorn master starting…")

def post_fork(server, worker):
    server.log.info(f"Worker spawned (pid: {worker.pid})")

def worker_exit(server, worker):
    server.log.info(f"Worker exiting (pid: {worker.pid})")
