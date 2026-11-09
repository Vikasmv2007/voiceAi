"""Small per-visitor rate limit, so nobody can burn your Gnani credits with a script.
Counts are kept in memory per server process (good enough for one restaurant)."""
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import jsonify, request

from app import config

_hits = defaultdict(deque)
_lock = threading.Lock()


def client_ip():
    if config.TRUST_PROXY:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.remote_addr or "?"


def allow(bucket, per_minute, now=None):
    now = time.monotonic() if now is None else now
    key = (bucket, client_ip())
    with _lock:
        q = _hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= per_minute:
            return False
        q.append(now)
        if len(_hits) > 5000:               # forget idle visitors
            for k in [k for k, v in _hits.items() if not v or now - v[-1] > 60][:2500]:
                _hits.pop(k, None)
        return True


def limit(bucket, per_minute_setting):
    """@limit("voice", "RATE_LIMIT_VOICE") -> 429 when one visitor calls too often."""
    def deco(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            per_minute = getattr(config, per_minute_setting)
            if per_minute > 0 and not allow(bucket, per_minute):
                return jsonify({"error": "Too many requests. Please wait a minute and try again."}), 429
            return view(*args, **kwargs)
        return wrapper
    return deco


def reset():
    with _lock:
        _hits.clear()
