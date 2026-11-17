import logging
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from agent.config import Settings, get_settings
from agent.contracts.idempotency import validate_key
from agent.contracts.types import ActorContext, ActorType
from agent.db import engine, get_session
from agent.identity.security import authenticate_bearer, authenticate_staff, issue_session
from agent.policy.service import PolicyResource, authorize
from agent.registry.schema import PublishedAgent
from agent.registry.service import PublishedVersionConflict, list_versions, load, publish

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)
app = FastAPI(title="Hospital Agent Platform", version="0.1.0")
bearer_scheme = HTTPBearer(auto_error=False)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message


def error_response(status: int, code: str, message: str, trace_id: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error_code": code, "message": message, "trace_id": trace_id})


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    incoming = request.headers.get("X-Trace-Id")
    try:
        request.state.trace_id = UUID(incoming) if incoming else uuid4()
    except ValueError:
        request.state.trace_id = uuid4()
    try:
        response = await call_next(request)
    except Exception as exc:
        log.error("Unhandled request error type=%s trace_id=%s", type(exc).__name__, request.state.trace_id)
        response = error_response(500, "internal_error", "Internal server error", str(request.state.trace_id))
    response.headers["X-Trace-Id"] = str(request.state.trace_id)
    log.info("request method=%s path=%s status=%s trace_id=%s", request.method, request.url.path,
             response.status_code, request.state.trace_id)
    return response


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return error_response(exc.status, exc.code, exc.message, str(request.state.trace_id))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return error_response(422, "validation_error", "Request validation failed", str(request.state.trace_id))


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    code = "not_found" if exc.status_code == 404 else "http_error"
    message = "Not found" if exc.status_code == 404 else "HTTP request failed"
    return error_response(exc.status_code, code, message, str(request.state.trace_id))


def require_idempotency_key(key: str | None = Header(default=None, alias="Idempotency-Key")) -> str:
    try:
        return validate_key(key)
    except ValueError:
        raise ApiError(400, "invalid_idempotency_key", "Invalid Idempotency-Key") from None


def get_actor(request: Request, db: Session = Depends(get_session),
              settings: Settings = Depends(get_settings),
              credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> ActorContext:
    authorization = f"Bearer {credentials.credentials}" if credentials else None
    actor = authenticate_bearer(db, settings, authorization, request.state.trace_id)
    if actor is None:
        raise ApiError(401, "unauthorized", "Authentication required")
    return actor


def require_policy(db: Session, actor: ActorContext, action: str, resource: PolicyResource) -> None:
    if not authorize(db, actor, action, resource):
        raise ApiError(403, "forbidden", "Access denied")


@app.get("/health/live")
def live():
    return {"status": "live"}


@app.get("/health/ready")
def ready(request: Request):
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        raise ApiError(503, "unavailable", "Database unavailable") from None
    return {"status": "ready", "trace_id": str(request.state.trace_id)}


class SessionResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    expires_at: str


class StaffLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1)


@app.post("/session/patient", response_model=SessionResponse, status_code=201)
def patient_session(db: Session = Depends(get_session), settings: Settings = Depends(get_settings)):
    token, row = issue_session(db, settings, uuid4(), ActorType.PATIENT, ["patient"])
    db.commit()
    return SessionResponse(token=token, expires_at=row.expires_at.isoformat())


@app.post("/session/staff", response_model=SessionResponse)
def staff_session(body: StaffLogin, db: Session = Depends(get_session), settings: Settings = Depends(get_settings)):
    account = authenticate_staff(db, settings, body.username, body.password)
    if account is None:
        raise ApiError(401, "unauthorized", "Invalid credentials")
    token, row = issue_session(db, settings, account.id, ActorType.STAFF, [account.role])
    db.commit()
    return SessionResponse(token=token, expires_at=row.expires_at.isoformat())


@app.get("/agents")
def agents(actor: ActorContext = Depends(get_actor), db: Session = Depends(get_session)):
    require_policy(db, actor, "agents:list", PolicyResource("agent_registry", None, actor.tenant_id))
    rows = list_versions(db, actor.tenant_id)
    return {"agents": [{"agent_id": row.agent_id, "version": row.version,
                        "published_at": row.published_at.isoformat()} for row in rows]}


@app.get("/agents/{agent_id}/versions/{version}")
def agent_version(agent_id: str, version: str, actor: ActorContext = Depends(get_actor), db: Session = Depends(get_session)):
    require_policy(db, actor, "agents:list", PolicyResource("agent_version", f"{agent_id}:{version}", actor.tenant_id))
    result = load(db, actor.tenant_id, agent_id, version)
    if result is None:
        raise ApiError(404, "not_found", "Agent version not found")
    return result


@app.post("/agents/versions", status_code=201)
def publish_agent(agent: PublishedAgent, actor: ActorContext = Depends(get_actor), db: Session = Depends(get_session)):
    require_policy(db, actor, "agents:publish", PolicyResource("agent_version", f"{agent.agent_id}:{agent.version}", actor.tenant_id))
    try:
        row = publish(db, actor.tenant_id, agent)
    except PublishedVersionConflict:
        raise ApiError(409, "version_conflict", "Agent version already published") from None
    return {"agent_id": row.agent_id, "version": row.version, "snapshot_hash": row.snapshot_hash}

