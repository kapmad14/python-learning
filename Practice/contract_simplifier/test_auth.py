# utils/auth.py
# Simple user management for testing stage.
# Stores users with hashed passwords in users.json (in project root).
#
# NOTE: This is intended for testing/pilots. For production use a proper auth provider.

import json
import os
import hashlib

USERS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "users.json")


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(data):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def register_user(username: str, password: str, plan="free"):
    users = _load_users()
    if username in users:
        raise ValueError("User already exists")
    users[username] = {
        "password_hash": _hash_password(password),
        "plan": plan
    }
    _save_users(users)


def validate_user(username: str, password: str):
    users = _load_users()
    if username not in users:
        return False
    return users[username]["password_hash"] == _hash_password(password)


def get_user_plan(username: str):
    users = _load_users()
    return users.get(username, {}).get("plan")


# Utility: create a default admin/test user if file missing
def ensure_default_user():
    users = _load_users()
    if not users:
        # default test user: test / test123 (plan: paid) — change before sharing
        users["test"] = {"password_hash": _hash_password("test123"), "plan": "paid"}
        _save_users(users)
