"""Level Lock simulator server using FastAPI.

Run locally to simulate the vendor backend that the Level Lock integration
connects to. It exposes the new ws-partner-server API:

- OAuth2 Device Code Flow:
  - `POST /oauth2/device-code/initiate` → starts device code flow
  - `POST /oauth2/device-code/verify` → verify user code with credentials
  - `POST /oauth2/device-code/token` → poll for access token

- WebSocket: `/v1/ws` for authenticated connections
  - Requires Bearer token authentication
  - Message types: ping/pong, list_devices, lock, unlock, get_device_state

- Debug HTTP:
  - `GET /v1/locks` → returns list of all locks
  - `POST /v1/locks` → create a new lock
  - `GET /v1/locks/{lock_id}` → returns lock state
  - `POST /v1/locks/{lock_id}` with JSON `{ "state": "locked"|"unlocked" }` →
    updates state and notifies all connected WebSocket clients
  - `DELETE /v1/locks/{lock_id}` → delete a lock

Usage:
  uvicorn homeassistant.components.levelhome.simulator_server:app \
    --reload --port 8081

This server is intentionally minimal and designed to match the message formats
expected in `homeassistant/components/levelhome/ws.py`.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from typing import Any
import uuid

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

LOGGER = logging.getLogger(__name__)

# =====================
# App and configuration
# =====================

app = FastAPI(title="Level Lock Simulator (WS-Partner API)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TOKEN_EXPIRES_IN: int = 3600
DEFAULT_USER_ID: str = "user@example.com"
DEFAULT_PASSWORD: str = "password123"

async def _require_bearer(request: Request) -> str:
    """Require a valid bearer token."""
    authorization = request.headers.get("authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    return token

# ======================
# In-memory device model
# ======================

class LockState:
    """Simple in-memory representation of a lock."""

    def __init__(self, lock_id: str, name: str | None = None) -> None:
        """Initialize lock state."""
        self.lock_id = lock_id
        self.name = name or f"Level Lock {lock_id}"
        self.state: str = "locked"
        self.battery_level: str = "good"
        self.reachable: bool = True
        self.door_sense: str = "closed"
        self._lock = asyncio.Lock()

    async def set_state(self, new_state: str) -> None:
        """Update lock state."""
        if new_state not in ("locked", "unlocked"):
            raise ValueError("State must be 'locked' or 'unlocked'")
        async with self._lock:
            self.state = new_state

    def to_device_dict(self, location_uuid: str = "loc-1") -> dict[str, Any]:
        """Convert to device list item format."""
        return {
            "device_uuid": self.lock_id,
            "name": self.name,
            "serial_number": f"SN-{self.lock_id}",
            "product": "lock",
            "location_uuid": location_uuid,
        }

    def get_state_dict(self) -> dict[str, Any]:
        """Get device state information."""
        return {
            "bolt_state": self.state,
            "battery_level": self.battery_level,
            "reachable": self.reachable,
            "door_sense": self.door_sense,
        }

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

    async def ensure_default_locks(self) -> list[LockState]:
        """Ensure at least 3 default locks exist."""
        async with self._lock:
            if self._locks:
                return list(self._locks.values())
            lock1 = LockState("sim-lock-1", name="Front Door")
            lock2 = LockState("sim-lock-2", name="Back Door")
            lock3 = LockState("sim-lock-3", name="Garage Door")
            self._locks[lock1.lock_id] = lock1
            self._locks[lock2.lock_id] = lock2
            self._locks[lock3.lock_id] = lock3
            return [lock1, lock2, lock3]

    async def create(
        self, *, lock_id: str | None = None, name: str | None = None
    ) -> LockState:
        """Create a new lock."""
        async with self._lock:
            if lock_id is None:
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

REGISTRY = LockRegistry()

# ===================================
# WebSocket connection management
# ===================================

class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        """Initialize connection manager."""
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Add a WebSocket connection."""
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to all connected clients."""
        async with self._lock:
            stale: list[WebSocket] = []
            for ws in list(self._connections):
                try:
                    await ws.send_json(message)
                except Exception:
                    stale.append(ws)
            for ws in stale:
                self._connections.discard(ws)

CONNECTION_MANAGER = ConnectionManager()

# ==========================
# OAuth2 Device Code Flow
# ==========================

class DeviceCodeRequest:
    """Track a device code request lifecycle."""

    def __init__(
        self,
        device_code: str,
        user_code: str,
        client_id: str,
        code_challenge: str | None,
        code_challenge_method: str | None,
        scope: str | None,
    ) -> None:
        """Initialize device code request."""
        self.device_code = device_code
        self.user_code = user_code
        self.client_id = client_id
        self.code_challenge = code_challenge
        self.code_challenge_method = code_challenge_method
        self.scope = scope
        self.verified = False
        self.created_at = time.time()

class OAuthStore:
    """In-memory store for OAuth2 device codes and tokens."""

    def __init__(self) -> None:
        """Initialize OAuth store."""
        self._device_codes: dict[str, DeviceCodeRequest] = {}
        self._access_tokens: set[str] = set()
        self._refresh_tokens: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create_device_code(
        self,
        *,
        client_id: str,
        code_challenge: str | None,
        code_challenge_method: str | None,
        scope: str | None,
    ) -> tuple[str, str]:
        """Create a new device code."""
        async with self._lock:
            device_code = str(uuid.uuid4())
            user_code = f"{secrets.randbelow(1000000):06d}"
            self._device_codes[device_code] = DeviceCodeRequest(
                device_code=device_code,
                user_code=user_code,
                client_id=client_id,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
                scope=scope,
            )
            return device_code, user_code

    async def verify_user_code(
        self, user_code: str, user_id: str, password: str
    ) -> bool:
        """Verify user code with credentials."""
        if user_id != DEFAULT_USER_ID or password != DEFAULT_PASSWORD:
            return False
        async with self._lock:
            for req in self._device_codes.values():
                if req.user_code == user_code:
                    req.verified = True
                    return True
            return False

    async def poll_device_code(self, device_code: str) -> dict[str, Any] | None:
        """Poll for device code authorization."""
        async with self._lock:
            req = self._device_codes.get(device_code)
            if req is None:
                return None
            if not req.verified:
                return {"pending": True}
            self._device_codes.pop(device_code)
            access_token = secrets.token_urlsafe(32)
            refresh_token = secrets.token_urlsafe(32)
            self._access_tokens.add(access_token)
            self._refresh_tokens[refresh_token] = {
                "client_id": req.client_id,
                "scope": req.scope or "all",
                "created_at": time.time(),
            }
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": TOKEN_EXPIRES_IN,
                "scope": req.scope or "all",
            }

    async def refresh(self, refresh_token: str) -> dict[str, Any]:
        """Refresh access token using refresh token."""
        async with self._lock:
            meta = self._refresh_tokens.get(refresh_token)
            if meta is None:
                LOGGER.warning("Refresh token not found, minting new token permissively")
                scope = "all"
            else:
                scope = meta.get("scope", "all")
                self._refresh_tokens.pop(refresh_token, None)

            new_access = secrets.token_urlsafe(32)
            new_refresh = secrets.token_urlsafe(32)
            self._access_tokens.add(new_access)
            self._refresh_tokens[new_refresh] = {
                "client_id": meta.get("client_id") if meta else None,
                "scope": scope,
                "created_at": time.time(),
            }
            token = {
                "access_token": new_access,
                "refresh_token": new_refresh,
                "token_type": "Bearer",
                "expires_in": TOKEN_EXPIRES_IN,
                "scope": scope,
            }
            LOGGER.info("Tokens refreshed (expires in %ss)", TOKEN_EXPIRES_IN)
            return token

OAUTH = OAuthStore()

# ==========================
# OAuth2 Device Code Routes
# ==========================

@app.post("/oauth2/device-code/initiate")
async def oauth_device_code_initiate(body: dict[str, Any]) -> JSONResponse:
    """Initiate OAuth2 device code flow."""
    client_id = body.get("client_id")
    code_challenge = body.get("code_challenge")
    code_challenge_method = body.get("code_challenge_method")
    scope = body.get("scope")

    if not client_id:
        raise HTTPException(status_code=400, detail="client_id required")

    device_code, user_code = await OAUTH.create_device_code(
        client_id=client_id,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        scope=scope,
    )

    LOGGER.info(
        "Device code initiated: device_code=%s, user_code=%s",
        device_code[:8],
        user_code,
    )

    return JSONResponse({
        "device_code": device_code,
        "user_code": user_code,
        "verification_uri": "http://localhost:8081/verify",
        "expires_in": 600,
        "interval": 5,
    })

@app.post("/oauth2/device-code/verify")
async def oauth_device_code_verify(body: dict[str, Any]) -> JSONResponse:
    """Verify user code with credentials."""
    client_id = body.get("client_id")
    user_code = body.get("user_code")
    user_id = body.get("user_id")
    password = body.get("password")

    if not all([client_id, user_code, user_id, password]):
        raise HTTPException(
            status_code=400,
            detail="client_id, user_code, user_id, password required"
        )

    success = await OAUTH.verify_user_code(user_code, user_id, password)

    if not success:
        LOGGER.warning("User code verification failed: user_code=%s", user_code)
        return JSONResponse(
            {"success": False, "message": "Invalid credentials or user code"},
            status_code=401
        )

    LOGGER.info("User code verified: user_code=%s", user_code)
    return JSONResponse({"success": True, "message": "User code verified"})

@app.post("/oauth2/device-code/token")
async def oauth_device_code_token(body: dict[str, Any]) -> JSONResponse:
    """Poll for device code authorization or refresh token."""
    grant_type = body.get("grant_type")

    if grant_type == "urn:ietf:params:oauth:grant-type:device_code":
        device_code = body.get("device_code")
        if not device_code:
            return JSONResponse(
                {"error": "invalid_request", "error_description": "device_code required"},
                status_code=400
            )

        result = await OAUTH.poll_device_code(device_code)
        if result is None:
            LOGGER.warning("Invalid device code: %s", device_code[:8])
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Invalid device code"},
                status_code=400
            )

        if result.get("pending"):
            return JSONResponse(
                {"error": "authorization_pending", "error_description": "User has not yet authorized"},
                status_code=400
            )

        LOGGER.info("Device code authorized, tokens issued")
        return JSONResponse(result)

    if grant_type == "refresh_token":
        refresh_token = body.get("refresh_token")
        if not refresh_token:
            return JSONResponse(
                {"error": "invalid_request", "error_description": "refresh_token required"},
                status_code=400
            )

        token = await OAUTH.refresh(refresh_token)
        return JSONResponse(token)

    LOGGER.warning("Unknown grant type, minting token permissively")
    token = await OAUTH.refresh("")
    return JSONResponse(token)

# ============================
# WebSocket protocol and routes
# ============================

@app.websocket("/v1/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Handle WebSocket connection."""
    authz = websocket.headers.get("authorization")
    if not authz or not authz.startswith("Bearer "):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    await CONNECTION_MANAGER.connect(websocket)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "list_devices":
                await REGISTRY.ensure_default_locks()
                locks = await REGISTRY.list_all()
                devices = [lock.to_device_dict() for lock in locks]
                await websocket.send_json({
                    "type": "list_devices_reply",
                    "devices": devices,
                })

            elif msg_type == "lock":
                device_uuid = data.get("device_uuid")
                if not device_uuid:
                    await websocket.send_json({
                        "type": "lock_reply",
                        "device_uuid": "",
                        "success": False,
                        "error": "device_uuid required",
                    })
                    continue

                lock = await REGISTRY.get(device_uuid)
                if lock is None:
                    await websocket.send_json({
                        "type": "lock_reply",
                        "device_uuid": device_uuid,
                        "success": False,
                        "error": "device not found",
                    })
                    continue

                await lock.set_state("locked")
                await websocket.send_json({
                    "type": "lock_reply",
                    "device_uuid": device_uuid,
                    "success": True,
                })

            elif msg_type == "unlock":
                device_uuid = data.get("device_uuid")
                if not device_uuid:
                    await websocket.send_json({
                        "type": "unlock_reply",
                        "device_uuid": "",
                        "success": False,
                        "error": "device_uuid required",
                    })
                    continue

                lock = await REGISTRY.get(device_uuid)
                if lock is None:
                    await websocket.send_json({
                        "type": "unlock_reply",
                        "device_uuid": device_uuid,
                        "success": False,
                        "error": "device not found",
                    })
                    continue

                await lock.set_state("unlocked")
                await websocket.send_json({
                    "type": "unlock_reply",
                    "device_uuid": device_uuid,
                    "success": True,
                })

            elif msg_type == "get_device_state":
                device_uuid = data.get("device_uuid")
                if not device_uuid:
                    await websocket.send_json({
                        "type": "get_device_state_reply",
                        "device_uuid": "",
                        "error": "device_uuid required",
                    })
                    continue

                lock = await REGISTRY.get(device_uuid)
                if lock is None:
                    await websocket.send_json({
                        "type": "get_device_state_reply",
                        "device_uuid": device_uuid,
                        "error": "device not found",
                    })
                    continue

                await websocket.send_json({
                    "type": "get_device_state_reply",
                    "device_uuid": device_uuid,
                    "device_state": lock.get_state_dict(),
                })

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await CONNECTION_MANAGER.disconnect(websocket)

# ===================
# Debug HTTP endpoints
# ===================

@app.get("/v1/locks")
async def list_locks(authorization: str | None = None) -> JSONResponse:
    """List all locks."""
    await REGISTRY.ensure_default_locks()
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
) -> JSONResponse:
    """Create a new lock."""
    name = body.get("name")
    lock_id = body.get("id")
    lock = await REGISTRY.create(lock_id=lock_id, name=name)
    return JSONResponse(
        {"id": lock.lock_id, "name": lock.name, "state": lock.state}, status_code=201
    )

@app.get("/v1/locks/{lock_id}")
async def get_lock(lock_id: str, authorization: str | None = None) -> JSONResponse:
    """Get lock details."""
    lock = await REGISTRY.get_or_create(lock_id)
    return JSONResponse({"lock_id": lock_id, "state": lock.state})

@app.post("/v1/locks/{lock_id}")
async def set_lock(
    lock_id: str,
    body: dict[str, Any],
    authorization: str | None = None,
) -> JSONResponse:
    """Set lock state."""
    state = body.get("state")
    if state not in ("locked", "unlocked"):
        raise HTTPException(
            status_code=400, detail="state must be 'locked' or 'unlocked'"
        )
    lock = await REGISTRY.get_or_create(lock_id)
    await lock.set_state(state)
    return JSONResponse({"lock_id": lock_id, "state": lock.state})

@app.post("/v1/locks/{lock_id}/lock")
async def command_lock(lock_id: str, authorization: str | None = None) -> JSONResponse:
    """Lock the lock."""
    lock = await REGISTRY.get_or_create(lock_id)
    await lock.set_state("locked")
    return JSONResponse({"result": "locked"})

@app.post("/v1/locks/{lock_id}/unlock")
async def command_unlock(
    lock_id: str, authorization: str | None = None
) -> JSONResponse:
    """Unlock the lock."""
    lock = await REGISTRY.get_or_create(lock_id)
    await lock.set_state("unlocked")
    return JSONResponse({"result": "unlocked"})

@app.delete("/v1/locks/{lock_id}")
async def delete_lock(lock_id: str, authorization: str | None = None) -> JSONResponse:
    """Delete a lock."""
    await REGISTRY.remove(lock_id)
    return JSONResponse({"result": "deleted"})

@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "name": "Level Lock Simulator (WS-Partner API)",
        "version": "2.0.0",
        "oauth2_device_code_initiate": "/oauth2/device-code/initiate",
        "oauth2_device_code_verify": "/oauth2/device-code/verify",
        "oauth2_device_code_token": "/oauth2/device-code/token",
        "websocket": "/v1/ws",
        "locks_list": "/v1/locks",
        "lock_create": "/v1/locks",
        "lock_get": "/v1/locks/{lock_id}",
        "lock_set": "/v1/locks/{lock_id}",
        "lock_command": "/v1/locks/{lock_id}/lock",
        "unlock_command": "/v1/locks/{lock_id}/unlock",
        "lock_delete": "/v1/locks/{lock_id}",
    }
