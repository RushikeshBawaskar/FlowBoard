from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from app.core.config import get_settings


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _base64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("utf-8"))


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    generated_salt = salt if salt is not None else secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        generated_salt.encode("utf-8"),
        100_000,
    )
    return digest.hex(), generated_salt


def verify_password(password: str, expected_hash: str, salt: str) -> bool:
    password_hash, _ = hash_password(password, salt=salt)
    return hmac.compare_digest(password_hash, expected_hash)


@dataclass(frozen=True)
class TokenPayload:
    sub: str
    email: str
    exp: int
    iat: int


def create_access_token(*, user_id: str, email: str) -> str:
    settings = get_settings()
    if settings.JWT_ALGORITHM != "HS256":
        raise ValueError("Unsupported JWT algorithm. Only HS256 is supported.")

    now = int(time.time())
    exp = now + (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)

    header = {"alg": settings.JWT_ALGORITHM, "typ": "JWT"}
    payload = {"sub": user_id, "email": email, "iat": now, "exp": exp}

    encoded_header = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = hmac.new(settings.JWT_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    encoded_signature = _base64url_encode(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def decode_access_token(token: str) -> TokenPayload:
    settings = get_settings()
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError as exc:
        raise ValueError("Invalid token format.") from exc

    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    expected_signature = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    provided_signature = _base64url_decode(encoded_signature)
    if not hmac.compare_digest(provided_signature, expected_signature):
        raise ValueError("Invalid token signature.")

    header = json.loads(_base64url_decode(encoded_header))
    if header.get("alg") != settings.JWT_ALGORITHM:
        raise ValueError("Invalid token algorithm.")

    payload = json.loads(_base64url_decode(encoded_payload))
    now = int(time.time())
    exp = int(payload.get("exp", 0))
    if exp <= now:
        raise ValueError("Token has expired.")

    sub = str(payload.get("sub", "")).strip()
    email = str(payload.get("email", "")).strip()
    iat = int(payload.get("iat", 0))
    if sub == "" or email == "":
        raise ValueError("Invalid token payload.")

    return TokenPayload(sub=sub, email=email, exp=exp, iat=iat)
