"""Authentication helpers — password hashing and role permissions."""
from __future__ import annotations

from typing import Optional

try:
    from werkzeug.security import check_password_hash, generate_password_hash
except ImportError:  # pragma: no cover
    import hashlib
    import secrets

    def generate_password_hash(password: str, method: str = "pbkdf2:sha256") -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
        return f"pbkdf2:sha256:260000${salt}${digest}"

    def check_password_hash(pwhash: str, password: str) -> bool:
        try:
            _method, salt, digest = pwhash.split("$", 2)
            iterations = int(_method.split(":")[-1]) if ":" in _method else 260000
            check = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), salt.encode(), iterations
            ).hex()
            return secrets.compare_digest(check, digest)
        except Exception:
            return False


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)


ROLE_PERMS = {
    "admin": {"read", "write", "admin", "delete"},
    "researcher": {"read", "write"},
    "viewer": {"read"},
}


def role_can(role: str, perm: str) -> bool:
    return perm in ROLE_PERMS.get(role, set())
