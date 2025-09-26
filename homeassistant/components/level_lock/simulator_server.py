"""Level Lock simulator server using FastAPI.

Run locally to simulate the vendor backend that the Level Lock integration
connects to. It exposes:

- WebSocket: `/v1/locks/{lock_id}/ws` for command exchange and state pushes
- Debug HTTP:
  - `GET /v1/locks/{lock_id}` → returns current state
  - `POST /v1/locks/{lock_id}` with JSON `{ "state": "locked"|"unlocked" }` →
    updates state and notifies all connected WebSocket clients

Authentication:
- Accepts an optional `Authorization: Bearer <token>` header but does not
  enforce validation by default. You can set REQUIRED_BEARER to a non-empty
  value to require a specific token.

Usage:
  uvicorn homeassistant.components.level_lock.simulator_server:app \
    --reload --port 8081

This server is intentionally minimal and designed to match the message formats
expected in `homeassistant/components/level_lock/ws.py`.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from typing import Any
import uuid

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

# =====================
# App and configuration
# =====================

app = FastAPI(title="Level Lock Simulator", version="1.0.0")

# Allow easy local testing from different origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Set this to a string to require that exact bearer token for all requests
REQUIRED_BEARER: str = ""


async def _require_bearer(authorization: str | None = None) -> None:
    """Optionally require a specific bearer token.

    If REQUIRED_BEARER is empty, this is a no-op. If non-empty, validates the
    header `Authorization: Bearer <token>`.
    """

    if not REQUIRED_BEARER:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != REQUIRED_BEARER:
        raise HTTPException(status_code=401, detail="Invalid bearer token")


# ======================
# In-memory device model
# ======================


class LockState:
    """Simple in-memory representation of a lock.

    - state: "locked" or "unlocked"
    - connections: set of active WebSocket connections
    """

    def __init__(self, lock_id: str, name: str | None = None) -> None:
        self.lock_id = lock_id
        self.name = name or f"Level Lock {lock_id}"
        self.state: str = "locked"
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def add_connection(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.add(ws)

    async def remove_connection(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)

    async def set_state(self, new_state: str, source: str = "digital") -> None:
        """Update state and notify all connected clients."""

        if new_state not in ("locked", "unlocked"):
            raise ValueError("State must be 'locked' or 'unlocked'")
        async with self._lock:
            self.state = new_state
            await self._broadcast_state_unlocked(source=source)

    async def _broadcast_state_unlocked(self, source: str = "digital") -> None:
        payload: dict[str, Any] = {
            "type": "state",
            "lock_id": self.lock_id,
            "state": self.state,
            "source": source,
        }
        stale: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self._connections.discard(ws)


class LockRegistry:
    """Registry for all simulated locks."""

    def __init__(self) -> None:
        self._locks: dict[str, LockState] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self, lock_id: str, *, name: str | None = None
    ) -> LockState:
        async with self._lock:
            lock = self._locks.get(lock_id)
            if lock is None:
                lock = LockState(lock_id, name=name)
                self._locks[lock_id] = lock
            return lock

    async def get(self, lock_id: str) -> LockState | None:
        async with self._lock:
            return self._locks.get(lock_id)

    async def list_all(self) -> list[LockState]:
        async with self._lock:
            return list(self._locks.values())

    async def ensure_default_lock(self) -> LockState:
        async with self._lock:
            if self._locks:
                # return an arbitrary lock
                return next(iter(self._locks.values()))
            # Create a default simulated device
            default = LockState("sim-lock-1", name="Front Door")
            self._locks[default.lock_id] = default
            return default


REGISTRY = LockRegistry()


# ==========================
# OAuth2 / PKCE mock backends
# ==========================


class AuthRequest:
    """Track an authorization request lifecycle keyed by request_uuid."""

    def __init__(
        self,
        client_id: str,
        redirect_uri: str,
        state: str | None,
        code_challenge: str | None,
        code_challenge_method: str | None,
        scope: str | None,
    ) -> None:
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.state = state
        self.code_challenge = code_challenge
        self.code_challenge_method = code_challenge_method
        self.scope = scope
        self.otp_confirmed = False
        self.permissions_granted = False


class OAuthStore:
    """In-memory store for OAuth2 authorization codes and tokens."""

    def __init__(self) -> None:
        self._auth_requests: dict[str, AuthRequest] = {}
        self._codes: dict[str, dict[str, Any]] = {}
        self._refresh_tokens: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create_auth_request(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        state: str | None,
        code_challenge: str | None,
        code_challenge_method: str | None,
        scope: str | None,
    ) -> str:
        async with self._lock:
            request_uuid = str(uuid.uuid4())
            self._auth_requests[request_uuid] = AuthRequest(
                client_id=client_id,
                redirect_uri=redirect_uri,
                state=state,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
                scope=scope,
            )
            return request_uuid

    async def mark_otp_confirmed(self, request_uuid: str) -> None:
        async with self._lock:
            req = self._auth_requests.get(request_uuid)
            if req is not None:
                req.otp_confirmed = True

    async def create_code(self, request_uuid: str) -> tuple[str, str]:
        async with self._lock:
            req = self._auth_requests.get(request_uuid)
            if req is None:
                raise HTTPException(status_code=400, detail="invalid_request_uuid")
            req.permissions_granted = True
            code = secrets.token_urlsafe(24)
            self._codes[code] = {
                "client_id": req.client_id,
                "redirect_uri": req.redirect_uri,
                "state": req.state,
                "scope": req.scope,
                # For PKCE we would bind code_challenge to code; we accept any verifier in this mock
                "code_challenge": req.code_challenge,
                "code_challenge_method": req.code_challenge_method,
                "created_at": time.time(),
            }
            return code, req.redirect_uri

    async def exchange_code(self, code: str) -> dict[str, Any]:
        async with self._lock:
            meta = self._codes.pop(code, None)
            if meta is None:
                raise HTTPException(status_code=400, detail="invalid_grant")
            access_token = secrets.token_urlsafe(32)
            refresh_token = secrets.token_urlsafe(32)
            token = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": meta.get("scope") or "all",
            }
            self._refresh_tokens[refresh_token] = {
                "client_id": meta.get("client_id"),
                "scope": token["scope"],
                "created_at": time.time(),
            }
            return token

    async def refresh(self, refresh_token: str) -> dict[str, Any]:
        async with self._lock:
            meta = self._refresh_tokens.get(refresh_token)
            if meta is None:
                # Permissive: mint a new token anyway for unknown refresh tokens
                scope = "all"
                new_access = secrets.token_urlsafe(32)
                new_refresh = secrets.token_urlsafe(32)
                token = {
                    "access_token": new_access,
                    "refresh_token": new_refresh,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": scope,
                }
                self._refresh_tokens[new_refresh] = {
                    "client_id": None,
                    "scope": scope,
                    "created_at": time.time(),
                }
                return token
            new_access = secrets.token_urlsafe(32)
            new_refresh = secrets.token_urlsafe(32)
            token = {
                "access_token": new_access,
                "refresh_token": new_refresh,
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": meta.get("scope") or "all",
            }
            # Rotate refresh token
            self._refresh_tokens.pop(refresh_token, None)
            self._refresh_tokens[new_refresh] = {
                "client_id": meta.get("client_id"),
                "scope": token["scope"],
                "created_at": time.time(),
            }
            return token


OAUTH = OAuthStore()


@app.get("/v1/authorize")
async def oauth_authorize(
    client_id: str,
    redirect_uri: str,
    response_type: str = "code",
    state: str | None = None,
    scope: str | None = None,
    code_challenge: str | None = None,
    code_challenge_method: str | None = None,
) -> HTMLResponse:
    # Create an auth request and return a tiny HTML page with hidden request_uuid
    if response_type != "code":
        # We only support authorization_code
        raise HTTPException(status_code=400, detail="unsupported_response_type")
    request_uuid = await OAUTH.create_auth_request(
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=state,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        scope=scope,
    )
    html = (
        "<html><body>"
        "<form>"
        f'<input type="hidden" name="request_uuid" value="{request_uuid}" />'
        "</form>"
        "</body></html>"
    )
    return HTMLResponse(content=html)


@app.post("/v1/oauth2/otp/start")
async def oauth_otp_start(body: dict[str, Any]) -> JSONResponse:
    # Accept any user_id/request_uuid and pretend we sent the OTP
    request_uuid = body.get("request_uuid")
    user_id = body.get("user_id")
    if not request_uuid or not user_id:
        raise HTTPException(status_code=400, detail="request_uuid and user_id required")
    # No-op; do not validate user_id in this mock
    return JSONResponse({"status": "otp_sent"})


@app.post("/v1/authenticate/otp/confirm")
async def oauth_otp_confirm(body: dict[str, Any]) -> JSONResponse:
    request_uuid = body.get("request_uuid")
    user_id = body.get("user_id")
    code = body.get("code")
    if not request_uuid or not user_id or not code:
        raise HTTPException(
            status_code=400, detail="request_uuid, user_id, code required"
        )
    await OAUTH.mark_otp_confirmed(str(request_uuid))
    return JSONResponse({"status": "otp_confirmed"})


@app.post("/v1/grant-permissions/accept")
async def oauth_grant_permissions(body: dict[str, Any]) -> JSONResponse:
    request_uuid = body.get("request_uuid")
    if not request_uuid:
        raise HTTPException(status_code=400, detail="request_uuid required")
    code, redirect_uri = await OAUTH.create_code(str(request_uuid))
    # Return a redirect URI including code and optional state query parameter
    # We do not URL-encode since typical redirect_uris are already valid and HA treats this as an opaque URL
    # However, we ensure correct concatenation of query parameters
    sep = "&" if ("?" in redirect_uri) else "?"
    state = (
        OAUTH._auth_requests.get(str(request_uuid)).state
        if str(request_uuid) in OAUTH._auth_requests
        else None
    )
    if state:
        redirect = f"{redirect_uri}{sep}code={code}&state={state}"
    else:
        redirect = f"{redirect_uri}{sep}code={code}"
    return JSONResponse({"redirect_uri": redirect})


@app.post("/v1/token/exchange")
async def oauth_token_exchange(request: Request) -> JSONResponse:
    # Accept form or JSON bodies
    payload: dict[str, Any] = {}
    try:
        form = await request.form()
        payload = dict(form)  # type: ignore[assignment]
    except Exception:
        pass
    if not payload:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    grant_type_val = payload.get("grant_type")
    grant_type = str(grant_type_val) if grant_type_val is not None else None

    # Infer grant_type if missing (permissive behavior for dev)
    if grant_type is None:
        if "code" in payload:
            grant_type = "authorization_code"
        elif "refresh_token" in payload:
            grant_type = "refresh_token"

    if grant_type == "authorization_code":
        code = payload.get("code") or payload.get("authorization_code")
        # Accept and ignore code_verifier for PKCE in this mock
        try:
            if code:
                token = await OAUTH.exchange_code(str(code))
            else:
                # Permissive mint when code is absent
                token = await OAUTH.refresh("")  # will mint permissively
        except HTTPException:
            # Permissive fallback if code not recognized
            token = await OAUTH.refresh("")
        return JSONResponse(token)

    if grant_type == "refresh_token":
        refresh_token_val = payload.get("refresh_token")
        token = await OAUTH.refresh(str(refresh_token_val or ""))
        return JSONResponse(token)

    # As a last resort, return a permissively minted token instead of 400
    token = await OAUTH.refresh("")
    return JSONResponse(token)


# ============================
# WebSocket protocol and routes
# ============================


@app.websocket("/v1/locks/{lock_id}/ws")
async def lock_websocket(lock_id: str, websocket: WebSocket) -> None:
    # Optionally check bearer from query header since WebSocket upgrades do not use Depends
    authz = websocket.headers.get("Authorization")
    if REQUIRED_BEARER:
        if not authz or not authz.startswith("Bearer "):
            await websocket.close(code=4401)
            return
        token = authz.removeprefix("Bearer ").strip()
        if token != REQUIRED_BEARER:
            await websocket.close(code=4401)
            return

    await websocket.accept()
    lock = await REGISTRY.get_or_create(lock_id)
    await lock.add_connection(websocket)

    # On connect, immediately send current state
    try:
        await websocket.send_json(
            {
                "type": "state",
                "lock_id": lock_id,
                "state": lock.state,
                "source": "snapshot",
            }
        )
    except Exception:
        await lock.remove_connection(websocket)
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            if msg_type == "command":
                command = data.get("command")
                request_id = data.get("request_id")
                if command not in ("lock", "unlock"):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "invalid_command",
                            "message": f"Unknown command: {command}",
                        }
                    )
                    continue

                # Ack accepted immediately
                await websocket.send_json(
                    {
                        "type": "ack",
                        "command": command,
                        "status": "accepted",
                        "request_id": request_id,
                    }
                )

                # Apply command
                target_state = "locked" if command == "lock" else "unlocked"
                await (await REGISTRY.get_or_create(lock_id)).set_state(
                    target_state, source="digital"
                )

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                # Ignore unknown types to keep parity with HA client behavior
                pass
    except WebSocketDisconnect:
        pass
    except Exception:
        # Swallow unexpected errors to avoid noisy logs in a dev server
        pass
    finally:
        await lock.remove_connection(websocket)


# ===================
# Debug HTTP endpoints
# ===================


@app.get("/v1/locks/{lock_id}/status")
async def get_lock_status(
    lock_id: str, authorization: str | None = None, _=Depends(_require_bearer)
) -> JSONResponse:  # type: ignore[override]
    lock = await REGISTRY.get_or_create(lock_id)
    return JSONResponse({"state": lock.state})


@app.get("/v1/locks")
async def list_locks(
    authorization: str | None = None, _=Depends(_require_bearer)
) -> JSONResponse:  # type: ignore[override]
    # Ensure at least one default lock exists
    await REGISTRY.ensure_default_lock()
    locks = await REGISTRY.list_all()
    payload = {
        "locks": [
            {"id": lock.lock_id, "name": lock.name, "state": lock.state}
            for lock in locks
        ]
    }
    return JSONResponse(payload)


@app.get("/v1/locks/{lock_id}")
async def get_lock(
    lock_id: str, authorization: str | None = None, _=Depends(_require_bearer)
) -> JSONResponse:  # type: ignore[override]
    lock = await REGISTRY.get_or_create(lock_id)
    return JSONResponse({"lock_id": lock_id, "state": lock.state})


@app.post("/v1/locks/{lock_id}")
async def set_lock(
    lock_id: str,
    body: dict[str, Any],
    authorization: str | None = None,
    _=Depends(_require_bearer),
) -> JSONResponse:  # type: ignore[override]
    state = body.get("state")
    if state not in ("locked", "unlocked"):
        raise HTTPException(
            status_code=400, detail="state must be 'locked' or 'unlocked'"
        )
    lock = await REGISTRY.get_or_create(lock_id)
    await lock.set_state(state, source="manual")
    return JSONResponse({"lock_id": lock_id, "state": lock.state})


@app.post("/v1/locks/{lock_id}/lock")
async def command_lock(
    lock_id: str, authorization: str | None = None, _=Depends(_require_bearer)
) -> JSONResponse:  # type: ignore[override]
    lock = await REGISTRY.get_or_create(lock_id)
    await lock.set_state("locked", source="http")
    return JSONResponse({"result": "locked"})


@app.post("/v1/locks/{lock_id}/unlock")
async def command_unlock(
    lock_id: str, authorization: str | None = None, _=Depends(_require_bearer)
) -> JSONResponse:  # type: ignore[override]
    lock = await REGISTRY.get_or_create(lock_id)
    await lock.set_state("unlocked", source="http")
    return JSONResponse({"result": "unlocked"})


# Convenience root
@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "name": "Level Lock Simulator",
        "oauth2_authorize": "/v1/authorize",
        "oauth2_token": "/v1/token/exchange",
        "oauth2_otp_start": "/v1/oauth2/otp/start",
        "oauth2_otp_confirm": "/v1/authenticate/otp/confirm",
        "oauth2_grant_accept": "/v1/grant-permissions/accept",
        "locks_list": "/v1/locks",
        "lock_status": "/v1/locks/{lock_id}/status",
        "lock_command": "/v1/locks/{lock_id}/lock",
        "unlock_command": "/v1/locks/{lock_id}/unlock",
        "websocket": "/v1/locks/{lock_id}/ws",
        "debug_get": "/v1/locks/{lock_id}",
        "debug_set": "/v1/locks/{lock_id}",
    }
