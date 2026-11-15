import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from agent.config import Settings
from agent.contracts.types import ActorContext, ActorType
from agent.identity.models import AuthSession, DemoAccount


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, expected_hex = encoded.split("$")
        if algorithm != "scrypt" or (int(n), int(r), int(p)) != (16384, 8, 1):
            return False
        actual = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(actual, bytes.fromhex(expected_hex))
    except (ValueError, TypeError):
        return False


def hash_token(token: str, settings: Settings) -> str:
    return hmac.new(settings.session_hash_key.encode("utf-8"), token.encode("ascii"), hashlib.sha256).hexdigest()


def issue_session(db: Session, settings: Settings, actor_id: UUID, actor_type: ActorType, roles: list[str]) -> tuple[str, AuthSession]:
    token = secrets.token_urlsafe(32)
    now = utc_now()
    row = AuthSession(
        id=uuid4(), tenant_id=settings.synthetic_tenant_id, actor_id=actor_id, actor_type=actor_type.value,
        roles=roles, token_hash=hash_token(token, settings), created_at=now,
        expires_at=now + timedelta(hours=settings.session_ttl_hours), revoked_at=None,
    )
    db.add(row)
    db.flush()
    return token, row


def authenticate_bearer(db: Session, settings: Settings, authorization: str | None, trace_id: UUID) -> ActorContext | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    if not token or any(ch.isspace() for ch in token) or not token.isascii():
        return None
    row = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token, settings)))
    if row is None:
        return None
    expiry = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if row.revoked_at is not None or expiry <= utc_now() or row.tenant_id != settings.synthetic_tenant_id:
        return None
    return ActorContext(actor_id=row.actor_id, actor_type=ActorType(row.actor_type), session_id=row.id,
                        tenant_id=row.tenant_id, roles=tuple(row.roles), trace_id=trace_id)


def authenticate_staff(db: Session, settings: Settings, username: str, password: str) -> DemoAccount | None:
    account = db.scalar(select(DemoAccount).where(DemoAccount.tenant_id == settings.synthetic_tenant_id,
                                                  DemoAccount.username == username))
    if account is None or not verify_password(password, account.password_hash):
        return None
    return account
