# utils/auth.py
"""
Streamlit-safe auth + in-memory usage helpers.

This version is robust across Streamlit releases:
- If st.experimental_singleton is available, we use it to create shared singletons.
- Otherwise we fall back to module-global dicts (process-level in-memory storage).

Public API:
- register_user(username, password, plan="free")
- validate_user(username, password) -> bool
- get_user_plan(username) -> str
- ensure_default_user()
- increment_usage(username, uploads=0, summaries=0)
- get_usage(username) -> {"uploads": int, "summaries": int}
- list_users() -> dict (admin/debug)
"""

from typing import Dict
import hashlib
import logging
import streamlit as st

logger = logging.getLogger(__name__)

# Attempt to use st.experimental_singleton if present, else fallback
try:
    _singleton_decorator = st.experimental_singleton  # type: ignore
except Exception:
    _singleton_decorator = None

if _singleton_decorator:
    @ _singleton_decorator
    def _get_user_store() -> Dict[str, Dict]:
        """Streamlit-backed singleton user store."""
        return {}
else:
    # fallback module-level dict
    _GLOBAL_USER_STORE: Dict[str, Dict] = {}

    def _get_user_store() -> Dict[str, Dict]:
        return _GLOBAL_USER_STORE

# Usage store (uploads/summaries)
if _singleton_decorator:
    @ _singleton_decorator
    def _get_usage_store() -> Dict[str, Dict[str, int]]:
        return {}
else:
    _GLOBAL_USAGE_STORE: Dict[str, Dict[str, int]] = {}

    def _get_usage_store() -> Dict[str, Dict[str, int]]:
        return _GLOBAL_USAGE_STORE

# Password hashing helper (simple salted SHA256 for testing only)
def _hash_password(username: str, password: str) -> str:
    if username is None or password is None:
        return ""
    s = (username + password).encode("utf-8")
    return hashlib.sha256(s).hexdigest()

# ---------- User management ----------
def register_user(username: str, password: str, plan: str = "free") -> None:
    """
    Register a new user. Raises ValueError if invalid or already exists.
    """
    if not username or not password:
        raise ValueError("username and password are required")

    users = _get_user_store()
    if username in users:
        raise ValueError("username already exists")

    plan = plan if plan in ("free", "paid") else "free"
    users[username] = {"pw_hash": _hash_password(username, password), "plan": plan}
    logger.info("Registered new user: %s (plan=%s)", username, plan)

def validate_user(username: str, password: str) -> bool:
    """
    Validate username/password. Returns True if valid else False.
    """
    if not username or not password:
        return False
    users = _get_user_store()
    u = users.get(username)
    if not u:
        return False
    return u.get("pw_hash") == _hash_password(username, password)

def get_user_plan(username: str) -> str:
    """
    Return the plan for the user (default 'free' if not found).
    """
    users = _get_user_store()
    u = users.get(username)
    if not u:
        return "free"
    return u.get("plan", "free")

def ensure_default_user():
    """
    Ensure a default test user exists.
    Username: 'test'  Password: 'test'
    """
    users = _get_user_store()
    if "test" not in users:
        users["test"] = {"pw_hash": _hash_password("test", "test"), "plan": "free"}
        logger.info("Default test user created: username='test', password='test'")

# ---------- Usage counters (in-memory) ----------
def increment_usage(username: str, uploads: int = 0, summaries: int = 0) -> None:
    """
    Increment usage counters for the username in the in-memory store.
    No filesystem writes.
    """
    if not username:
        return
    try:
        store = _get_usage_store()
        entry = store.get(username)
        if not entry:
            entry = {"uploads": 0, "summaries": 0}
        entry["uploads"] = entry.get("uploads", 0) + int(uploads)
        entry["summaries"] = entry.get("summaries", 0) + int(summaries)
        store[username] = entry
        logger.debug("increment_usage: %s -> %s", username, entry)
    except Exception as e:
        logger.exception("increment_usage failed: %s", e)

def get_usage(username: str) -> Dict[str, int]:
    """
    Return usage dict for username. If absent, returns {"uploads":0,"summaries":0}.
    """
    if not username:
        return {"uploads": 0, "summaries": 0}
    try:
        store = _get_usage_store()
        return store.get(username, {"uploads": 0, "summaries": 0})
    except Exception as e:
        logger.exception("get_usage failed: %s", e)
        return {"uploads": 0, "summaries": 0}

def list_users() -> Dict[str, Dict]:
    """
    Return a shallow copy of the user store for debugging.
    """
    users = _get_user_store()
    return dict(users)
