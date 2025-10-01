# utils/auth.py
"""
Simple in-memory user + usage management for the Contract Simplifier MVP.

- No filesystem dependencies (suitable for Streamlit Cloud and local testing).
- Provides: register_user, validate_user, get_user_plan, ensure_default_user,
  increment_usage, get_usage.

Security:
- Passwords are stored as salted SHA256 hashes (username used as salt) for basic safety.
- For production, replace with bcrypt/argon2 and a persistent database.
"""

from typing import Dict
import hashlib
import logging
import streamlit as st

logger = logging.getLogger(__name__)

# ---------- In-memory user store (singleton) ----------
@st.experimental_singleton
def _get_user_store() -> Dict[str, Dict]:
    """
    Returns a dict mapping username -> {"pw_hash": str, "plan": "free"|"paid", ...}
    Stored in-memory for the running app instance only.
    """
    return {}

# ---------- In-memory usage store (singleton) ----------
@st.experimental_singleton
def _get_usage_store() -> Dict[str, Dict[str, int]]:
    """
    Returns a dict mapping username -> {"uploads": int, "summaries": int}
    """
    return {}

# ---------- Password hashing helper ----------
def _hash_password(username: str, password: str) -> str:
    """
    Lightweight salted hash: SHA256(username + password).
    Replace with bcrypt/argon2 for production.
    """
    if username is None or password is None:
        return ""
    s = (username + password).encode("utf-8")
    return hashlib.sha256(s).hexdigest()

# ---------- User management API ----------
def register_user(username: str, password: str, plan: str = "free") -> None:
    """
    Register a new user. Raises ValueError if username invalid or already exists.
    """
    if not username or not password:
        raise ValueError("username and password are required")

    users = _get_user_store()
    if username in users:
        raise ValueError("username already exists")

    plan = plan if plan in ("free", "paid") else "free"
    users[username] = {"pw_hash": _hash_password(username, password), "plan": plan}
    # update singleton store
    # Note: directly mutating the returned dict updates the singleton
    logger.info("Registered new user: %s (plan=%s)", username, plan)

def validate_user(username: str, password: str) -> bool:
    """
    Validate username/password. Returns True if valid, else False.
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
    Ensure a default test user exists for quick testing.
    Username: 'test'  Password: 'test'
    (You can change this as needed.)
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
    store = _get_usage_store()
    entry = store.get(username)
    if not entry:
        entry = {"uploads": 0, "summaries": 0}
    entry["uploads"] = entry.get("uploads", 0) + int(uploads)
    entry["summaries"] = entry.get("summaries", 0) + int(summaries)
    store[username] = entry
    logger.debug("increment_usage: %s -> %s", username, entry)

def get_usage(username: str) -> Dict[str, int]:
    """
    Return usage dict for username. If absent, returns {"uploads":0,"summaries":0}.
    """
    if not username:
        return {"uploads": 0, "summaries": 0}
    store = _get_usage_store()
    return store.get(username, {"uploads": 0, "summaries": 0})

# ---------- (Optional helper) For admin/debug only ----------
def list_users() -> Dict[str, Dict]:
    """
    Return a shallow copy of the user store for debugging.
    """
    users = _get_user_store()
    return dict(users)
