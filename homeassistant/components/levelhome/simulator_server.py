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
  uvicorn homeassistant.components.levelhome.simulator_server:app \
    --reload --port 8081

This server is intentionally minimal and designed to match the message formats
expected in `homeassistant/components/levelhome/ws.py`.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
import secrets
import time
from typing import Any
import urllib.parse
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

LOGGER = logging.getLogger(__name__)

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
TOKEN_EXPIRES_IN: int = 3600


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
        """Initialize lock state."""
        self.lock_id = lock_id
        self.name = name or f"Level Lock {lock_id}"
        self.state: str = "locked"
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def add_connection(self, ws: WebSocket) -> None:
        """Add a WebSocket connection."""
        async with self._lock:
            self._connections.add(ws)

    async def remove_connection(self, ws: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            self._connections.discard(ws)

    async def close_all_connections(self) -> None:
        """Close all WebSocket connections."""
        async with self._lock:
            stale = list(self._connections)
            for ws in stale:
                with suppress(Exception):
                    await ws.close()
            self._connections.clear()

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
            except Exception:  # noqa: BLE001
                stale.append(ws)
        for ws in stale:
            self._connections.discard(ws)


class LockRegistry:
    """Registry for all simulated locks."""

    def __init__(self) -> None:
        """Initialize lock registry."""
        self._locks: dict[str, LockState] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self, lock_id: str, *, name: str | None = None
    ) -> LockState:
        """Get or create a lock by ID."""
        async with self._lock:
            lock = self._locks.get(lock_id)
            if lock is None:
                lock = LockState(lock_id, name=name)
                self._locks[lock_id] = lock
            return lock

    async def get(self, lock_id: str) -> LockState | None:
        """Get a lock by ID."""
        async with self._lock:
            return self._locks.get(lock_id)

    async def list_all(self) -> list[LockState]:
        """List all locks."""
        async with self._lock:
            return list(self._locks.values())

    async def ensure_default_lock(self) -> LockState:
        """Ensure at least one default lock exists."""
        async with self._lock:
            if self._locks:
                # return an arbitrary lock
                return next(iter(self._locks.values()))
            # Create a default simulated device
            default = LockState("sim-lock-1", name="Front Door")
            self._locks[default.lock_id] = default
            return default

    async def create(
        self, *, lock_id: str | None = None, name: str | None = None
    ) -> LockState:
        """Create a new lock."""
        async with self._lock:
            if lock_id is None:
                # Generate a unique simple id
                base = "sim-lock-"
                idx = 1
                while f"{base}{idx}" in self._locks:
                    idx += 1
                lock_id = f"{base}{idx}"
            if lock_id in self._locks:
                raise HTTPException(status_code=409, detail="lock_id already exists")
            lock = LockState(lock_id, name=name or f"Level Lock {lock_id}")
            self._locks[lock_id] = lock
            return lock

    async def remove(self, lock_id: str) -> None:
        """Remove a lock by ID."""
        async with self._lock:
            lock = self._locks.pop(lock_id, None)
        if lock is None:
            raise HTTPException(status_code=404, detail="not_found")
        # Close any websocket connections
        await lock.close_all_connections()


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
        """Initialize auth request."""
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
        """Initialize OAuth store."""
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
        """Create a new authorization request."""
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
        """Mark OTP as confirmed for request."""
        async with self._lock:
            req = self._auth_requests.get(request_uuid)
            if req is not None:
                req.otp_confirmed = True

    async def get_request_state(self, request_uuid: str) -> str | None:
        """Get the state parameter for an authorization request."""
        async with self._lock:
            req = self._auth_requests.get(request_uuid)
            return req.state if req is not None else None

    async def create_code(self, request_uuid: str) -> tuple[str, str]:
        """Create authorization code for request."""
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
        """Exchange authorization code for tokens."""
        async with self._lock:
            meta = self._codes.pop(code, None)
            if meta is None:
                LOGGER.error("Token exchange failed: invalid or expired code")
                raise HTTPException(status_code=400, detail="invalid_grant")

            access_token = secrets.token_urlsafe(32)
            refresh_token = secrets.token_urlsafe(32)
            token = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": TOKEN_EXPIRES_IN,
                "scope": meta.get("scope") or "all",
            }
            self._refresh_tokens[refresh_token] = {
                "client_id": meta.get("client_id"),
                "scope": token["scope"],
                "created_at": time.time(),
            }
            now = time.time()
            expires_at = now + TOKEN_EXPIRES_IN
            valid_duration = TOKEN_EXPIRES_IN - 20
            LOGGER.info("Initial tokens issued (expires in %ss)", TOKEN_EXPIRES_IN)
            LOGGER.debug(
                "Token: expires_at=%.1f, valid_for=%.1fs (after 20s buffer)",
                expires_at,
                valid_duration,
            )
            return token

    async def refresh(self, refresh_token: str) -> dict[str, Any]:
        """Refresh access token using refresh token."""
        async with self._lock:
            meta = self._refresh_tokens.get(refresh_token)

            # Debug info only if token not found (server restart scenario)
            if meta is None:
                stored_tokens = list(self._refresh_tokens.keys())
                if stored_tokens:
                    LOGGER.warning(
                        "Refresh token not in store (%s other tokens present)",
                        len(stored_tokens),
                    )
                else:
                    LOGGER.warning(
                        "No refresh tokens stored (server may have restarted)"
                    )
            if meta is None:
                # Permissive: mint a new token anyway for unknown refresh tokens
                # This can happen if the server restarted and lost in-memory state
                LOGGER.warning(
                    "Minting new token (permissive mode - server may have restarted)"
                )
                scope = "all"
                new_access = secrets.token_urlsafe(32)
                new_refresh = secrets.token_urlsafe(32)
                token = {
                    "access_token": new_access,
                    "refresh_token": new_refresh,
                    "token_type": "Bearer",
                    "expires_in": TOKEN_EXPIRES_IN,
                    "scope": scope,
                }
                self._refresh_tokens[new_refresh] = {
                    "client_id": None,
                    "scope": scope,
                    "created_at": time.time(),
                }
                LOGGER.info("New tokens issued (expires in %ss)", TOKEN_EXPIRES_IN)
                return token

            # Don't print verbose info for successful refreshes - they're expected

            new_access = secrets.token_urlsafe(32)
            new_refresh = secrets.token_urlsafe(32)
            token = {
                "access_token": new_access,
                "refresh_token": new_refresh,
                "token_type": "Bearer",
                "expires_in": TOKEN_EXPIRES_IN,
                "scope": meta.get("scope") or "all",
            }
            # Rotate refresh token
            self._refresh_tokens.pop(refresh_token, None)
            self._refresh_tokens[new_refresh] = {
                "client_id": meta.get("client_id"),
                "scope": token["scope"],
                "created_at": time.time(),
            }
            LOGGER.info("Tokens refreshed (new token expires in %ss)", TOKEN_EXPIRES_IN)
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
    """Handle OAuth2 authorization request."""
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
    """Start OTP flow."""
    # Accept any user_id/request_uuid and pretend we sent the OTP
    request_uuid = body.get("request_uuid")
    user_id = body.get("user_id")
    if not request_uuid or not user_id:
        raise HTTPException(status_code=400, detail="request_uuid and user_id required")
    # No-op; do not validate user_id in this mock
    return JSONResponse({"status": "otp_sent"})


@app.post("/v1/authenticate/otp/confirm")
async def oauth_otp_confirm(body: dict[str, Any]) -> JSONResponse:
    """Confirm OTP code."""
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
    """Accept permission grant and return authorization code."""
    request_uuid = body.get("request_uuid")
    if not request_uuid:
        raise HTTPException(status_code=400, detail="request_uuid required")
    code, redirect_uri = await OAUTH.create_code(str(request_uuid))
    # Return a redirect URI including code and optional state query parameter
    # We do not URL-encode since typical redirect_uris are already valid and HA treats this as an opaque URL
    # However, we ensure correct concatenation of query parameters
    sep = "&" if ("?" in redirect_uri) else "?"
    state = await OAUTH.get_request_state(str(request_uuid))
    if state:
        redirect = f"{redirect_uri}{sep}code={code}&state={state}"
    else:
        redirect = f"{redirect_uri}{sep}code={code}"
    return JSONResponse({"redirect_uri": redirect})


@app.post("/v1/token/exchange")
async def oauth_token_exchange(request: Request) -> JSONResponse:
    """Exchange authorization code or refresh token for access token."""
    # Accept form or JSON bodies
    payload: dict[str, Any] = {}

    content_type = request.headers.get("content-type", "")

    # Manually parse application/x-www-form-urlencoded if python-multipart is not available
    if "application/x-www-form-urlencoded" in content_type:
        with suppress(Exception):
            body = await request.body()
            # Parse form-urlencoded data manually
            decoded = body.decode("utf-8")
            payload = dict(urllib.parse.parse_qsl(decoded))
            # Don't print form parsing success - too verbose
    elif "application/json" in content_type:
        with suppress(Exception):
            payload = await request.json()
            if payload:
                LOGGER.debug("Parsed as JSON: %s", list(payload.keys()))
    else:
        # Try FastAPI's form parser if available (requires python-multipart)
        with suppress(Exception):
            form = await request.form()
            payload = dict(form)
            if payload:
                LOGGER.debug("Parsed as form data: %s", list(payload.keys()))

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
        LOGGER.info(
            "Authorization code exchange: code=%s",
            str(code)[:8] if code else "None",
        )
        # Accept and ignore code_verifier for PKCE in this mock
        try:
            if code:
                token = await OAUTH.exchange_code(str(code))
            else:
                # Permissive mint when code is absent
                LOGGER.warning("No code provided, minting token permissively")
                token = await OAUTH.refresh("")  # will mint permissively
        except HTTPException:
            # Permissive fallback if code not recognized
            LOGGER.warning("Code not recognized, minting token permissively")
            token = await OAUTH.refresh("")
        return JSONResponse(token)

    if grant_type == "refresh_token":
        refresh_token_val = payload.get("refresh_token")
        now = time.time()
        LOGGER.info(
            "Refresh token request: refresh_token=%s",
            str(refresh_token_val)[:8] if refresh_token_val else "None",
        )
        LOGGER.debug(
            "Note: Token refresh happens when access token expires or is about to expire"
        )
        token = await OAUTH.refresh(str(refresh_token_val or ""))
        # Debug: Show when the new token will expire and how long it's valid
        expires_in = token.get("expires_in", 0)
        expires_at = now + expires_in
        # Home Assistant requires: expires_at > (time.time() + 20)
        # So valid duration = expires_at - (now + 20) = expires_in - 20
        valid_duration = expires_in - 20
        LOGGER.debug(
            "New token: expires_in=%ss, expires_at=%.1f, valid_for=%.1fs (after 20s buffer)",
            expires_in,
            expires_at,
            valid_duration,
        )
        return JSONResponse(token)

    # As a last resort, return a permissively minted token instead of 400
    LOGGER.warning("Unknown grant type, minting token permissively")
    token = await OAUTH.refresh("")
    return JSONResponse(token)


# ============================
# WebSocket protocol and routes
# ============================


@app.websocket("/v1/locks/{lock_id}/ws")
async def lock_websocket(lock_id: str, websocket: WebSocket) -> None:
    """Handle WebSocket connection for lock."""
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
    except Exception:  # noqa: BLE001
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
    except Exception:  # noqa: BLE001
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
) -> JSONResponse:
    """Get lock status."""
    lock = await REGISTRY.get_or_create(lock_id)
    return JSONResponse({"state": lock.state})


@app.get("/v1/locks")
async def list_locks(
    authorization: str | None = None, _=Depends(_require_bearer)
) -> JSONResponse:
    """List all locks."""
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


@app.post("/v1/locks")
async def create_lock(
    body: dict[str, Any],
    authorization: str | None = None,
    _=Depends(_require_bearer),
) -> JSONResponse:
    """Create a new lock."""
    name = body.get("name")
    lock_id = body.get("id")
    lock = await REGISTRY.create(lock_id=lock_id, name=name)
    return JSONResponse(
        {"id": lock.lock_id, "name": lock.name, "state": lock.state}, status_code=201
    )


@app.get("/v1/locks/{lock_id}")
async def get_lock(
    lock_id: str, authorization: str | None = None, _=Depends(_require_bearer)
) -> JSONResponse:
    """Get lock details."""
    lock = await REGISTRY.get_or_create(lock_id)
    return JSONResponse({"lock_id": lock_id, "state": lock.state})


@app.post("/v1/locks/{lock_id}")
async def set_lock(
    lock_id: str,
    body: dict[str, Any],
    authorization: str | None = None,
    _=Depends(_require_bearer),
) -> JSONResponse:
    """Set lock state."""
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
) -> JSONResponse:
    """Lock the lock."""
    lock = await REGISTRY.get_or_create(lock_id)
    await lock.set_state("locked", source="http")
    return JSONResponse({"result": "locked"})


@app.post("/v1/locks/{lock_id}/unlock")
async def command_unlock(
    lock_id: str, authorization: str | None = None, _=Depends(_require_bearer)
) -> JSONResponse:
    """Unlock the lock."""
    lock = await REGISTRY.get_or_create(lock_id)
    await lock.set_state("unlocked", source="http")
    return JSONResponse({"result": "unlocked"})


@app.delete("/v1/locks/{lock_id}")
async def delete_lock(
    lock_id: str, authorization: str | None = None, _=Depends(_require_bearer)
) -> JSONResponse:
    """Delete a lock."""
    await REGISTRY.remove(lock_id)
    return JSONResponse({"result": "deleted"})


# Convenience root
@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "name": "Level Lock Simulator",
        "oauth2_authorize": "/v1/authorize",
        "oauth2_token": "/v1/token/exchange",
        "oauth2_otp_start": "/v1/oauth2/otp/start",
        "oauth2_otp_confirm": "/v1/authenticate/otp/confirm",
        "oauth2_grant_accept": "/v1/grant-permissions/accept",
        "locks_list": "/v1/locks",
        "lock_create": "/v1/locks",
        "lock_status": "/v1/locks/{lock_id}/status",
        "lock_command": "/v1/locks/{lock_id}/lock",
        "unlock_command": "/v1/locks/{lock_id}/unlock",
        "lock_delete": "/v1/locks/{lock_id}",
        "websocket": "/v1/locks/{lock_id}/ws",
        "debug_get": "/v1/locks/{lock_id}",
        "debug_set": "/v1/locks/{lock_id}",
    }
