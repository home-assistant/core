"""Credential-bound inbound WebSocket connections for remote Shelly devices."""

import asyncio
from dataclasses import dataclass, field
import hashlib
from http import HTTPStatus
from ipaddress import ip_address
import logging
import re
import secrets
from typing import Any

from aiohttp import WSMsgType, web
from aioshelly.rpc_device import WsServer
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import singleton
from homeassistant.helpers.http import HomeAssistantView
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CONNECTION_TYPE,
    CONF_REMOTE_CREDENTIAL,
    CONNECTION_REMOTE_WS,
    DOMAIN,
)

REMOTE_WS_URL = "/api/shelly/remote"
PAIRING_TIMEOUT = 600
IDENTIFY_TIMEOUT = 10
MAX_IDENTIFY_CONNECTIONS = 16
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")
MAC_PATTERN = re.compile(r"[0-9A-Fa-f]{12}")
REMOTE_URL_PATTERN = re.compile(
    r"(?:https?://[^\s\"'<>]*|wss?://[^\s\"'<>]*)?/api/shelly/remote\?[^\s\"'<>]*"
)
REMOTE_LOGGERS = (
    "homeassistant.helpers.http",
    "homeassistant.components.http.auth",
    "homeassistant.components.http.ban",
    "homeassistant.components.http.security_filter",
    "homeassistant.components.shelly",
    "homeassistant.config_entries",
    "homeassistant.data_entry_flow",
    "aiohttp.access",
    "aiohttp.server",
    "aioshelly.rpc_device.wsrpc",
    "aioshelly.rpc_device.device",
)


@callback
def redact_remote_url(value: str) -> str:
    """Redact complete pairing URLs, including relative URLs in access logs."""
    return REMOTE_URL_PATTERN.sub("[REDACTED REMOTE URL]", value)


class RemoteURLLogFilter(logging.Filter):
    """Redact pairing URLs at the audited HA and aiohttp logging sources."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact formatted arguments and exception text without retaining tokens."""
        record.msg = redact_remote_url(record.getMessage())
        record.args = ()
        if record.exc_info:
            record.exc_text = redact_remote_url(
                logging.Formatter().formatException(record.exc_info)
            )
        if record.stack_info:
            record.stack_info = redact_remote_url(record.stack_info)
        return True


REMOTE_LOG_FILTER = RemoteURLLogFilter()


@callback
def is_remote_entry(entry: ConfigEntry) -> bool:
    """Return whether this entry uses an authorized remote transport."""
    return entry.data.get(CONF_CONNECTION_TYPE) == CONNECTION_REMOTE_WS


@callback
def validate_external_url(value: str) -> URL:
    """Validate a public HTTPS origin without attempting to access it."""
    url = URL(value)
    if (
        url.scheme != "https"
        or not url.host
        or url.user is not None
        or url.query
        or url.fragment
        or url.path not in ("", "/")
        or url.host == "localhost"
        or url.host.endswith(".local")
    ):
        raise ValueError("A public HTTPS origin is required")
    try:
        address = ip_address(url.host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError("A public HTTPS origin is required")
    return url


@callback
def get_external_url(hass: HomeAssistant) -> str:
    """Get the configured external HTTPS URL, excluding local URLs."""
    try:
        value = get_url(hass, require_ssl=True, allow_internal=False, allow_cloud=True)
        return str(validate_external_url(value))
    except NoURLAvailableError, ValueError:
        return ""


@dataclass(slots=True)
class RemoteCredential:
    """State associated with a credential hash; never stores the raw token."""

    digest: str
    device_id: str | None = None
    entry_id: str | None = None
    info: dict[str, Any] | None = None
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    expires_at: float | None = None
    identifying: bool = False
    websockets: set[web.WebSocketResponse] = field(default_factory=set)
    reconnect_count: int = 0
    last_connected: str | None = None
    last_disconnected: str | None = None


class RemoteConnectionManager:
    """Authorize sockets before attaching them to persistent RPC transports."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the manager."""
        for name in REMOTE_LOGGERS:
            logging.getLogger(name).addFilter(REMOTE_LOG_FILTER)
        self.hass = hass
        self.server = WsServer()
        self.credentials: dict[str, RemoteCredential] = {}
        self._identifying = 0

    @callback
    def create_credential(self, origin: URL) -> tuple[RemoteCredential, str]:
        """Create a temporary pairing credential and its one-time connection URL."""
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        record = RemoteCredential(
            digest, expires_at=asyncio.get_running_loop().time() + PAIRING_TIMEOUT
        )
        self.credentials[digest] = record
        url = origin.with_scheme("wss").with_path(REMOTE_WS_URL)
        return record, str(url.with_query(remote_key=token))

    @callback
    def register_entry(self, entry: ConfigEntry) -> RemoteCredential | None:
        """Restore a bound credential from config entry data."""
        if (
            not (digest := entry.data.get(CONF_REMOTE_CREDENTIAL))
            or not entry.unique_id
        ):
            return None
        record = self.credentials.setdefault(
            digest, RemoteCredential(digest, device_id=entry.unique_id.upper())
        )
        record.entry_id = entry.entry_id
        record.device_id = entry.unique_id.upper()
        record.expires_at = None
        return record

    @callback
    def lookup(self, token: str) -> RemoteCredential | None:
        """Look up an unexpired credential without retaining the secret."""
        if not TOKEN_PATTERN.fullmatch(token):
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        record = self.credentials.get(digest)
        if record is None or not secrets.compare_digest(record.digest, digest):
            return None
        if record.expires_at is not None and (
            record.expires_at <= asyncio.get_running_loop().time()
        ):
            return None
        return record

    async def revoke(self, digest: str) -> None:
        """Revoke admission first, then close every socket using this credential."""
        if (record := self.credentials.pop(digest, None)) is None:
            return
        for websocket in tuple(record.websockets):
            await websocket.close(code=1008)

    async def _identify(self, websocket: web.WebSocketResponse) -> dict[str, Any]:
        """Query device identity on the candidate socket before routing any traffic."""
        await websocket.send_json(
            {"id": 0, "src": "ha-shelly-identify", "method": "Shelly.GetDeviceInfo"}
        )
        async with asyncio.timeout(IDENTIFY_TIMEOUT):
            for _ in range(32):
                message = await websocket.receive()
                if message.type is not WSMsgType.TEXT:
                    raise ValueError("Invalid identity response")
                frame = message.json()
                if not isinstance(frame, dict):
                    raise TypeError("Invalid identity response")
                if frame.get("method") is not None:
                    continue
                if type(frame.get("id")) is not int or frame["id"] != 0:
                    continue
                info = frame.get("result")
                if not isinstance(info, dict):
                    raise TypeError("Invalid identity response")
                mac, hostname = info.get("mac"), info.get("id")
                if (
                    not isinstance(mac, str)
                    or not MAC_PATTERN.fullmatch(mac)
                    or not isinstance(hostname, str)
                    or not hostname.rpartition("-")[2].upper() == mac.upper()
                    or frame.get("src") != hostname
                    or info.get("gen") not in (2, 3, 4)
                    or not isinstance(info.get("model"), str)
                    or not isinstance(info.get("fw_id"), str)
                ):
                    raise ValueError("Invalid identity response")
                return info
        raise ValueError("Invalid identity response")

    async def accept(
        self, request: web.Request, record: RemoteCredential
    ) -> web.StreamResponse:
        """Verify a candidate socket and run it on the authorized server."""
        if record.identifying or self._identifying >= MAX_IDENTIFY_CONNECTIONS:
            return web.Response(status=HTTPStatus.TOO_MANY_REQUESTS)
        record.identifying = True
        identifying = True
        self._identifying += 1
        websocket = web.WebSocketResponse(
            protocols=["json-rpc"], heartbeat=30, max_msg_size=1024 * 1024
        )
        record.websockets.add(websocket)
        try:
            await websocket.prepare(request)
            try:
                info = await self._identify(websocket)
            except ValueError, TypeError, TimeoutError, ConnectionError:
                await websocket.close(code=1008)
                return websocket
            finally:
                record.identifying = False
                identifying = False
                self._identifying -= 1
            mac = info["mac"].upper()
            if (
                self.credentials.get(record.digest) is not record
                or (
                    record.expires_at is not None
                    and record.expires_at <= asyncio.get_running_loop().time()
                )
                or (record.device_id is not None and record.device_id != mac)
                or any(
                    entry.unique_id == mac and entry.entry_id != record.entry_id
                    for entry in self.hass.config_entries.async_entries(DOMAIN)
                )
                or any(
                    other is not record
                    and other.device_id == mac
                    and (record.entry_id is None or other.entry_id != record.entry_id)
                    for other in self.credentials.values()
                )
            ):
                await websocket.close(code=1008)
                return websocket
            record.device_id = mac
            record.info = info
            if record.last_connected is not None:
                record.reconnect_count += 1
            record.last_connected = dt_util.utcnow().isoformat()
            handler = self.hass.async_create_background_task(
                self.server.handle_connection(websocket, mac, info["id"]),
                "Shelly remote connection",
                eager_start=True,
            )
            record.ready.set()
            await handler
            return websocket
        finally:
            if identifying:
                record.identifying = False
                self._identifying -= 1
            record.websockets.discard(websocket)
            record.last_disconnected = dt_util.utcnow().isoformat()


class ShellyRemoteReceiver(HomeAssistantView):
    """Receive remote connections secured by a dedicated bearer credential."""

    url = REMOTE_WS_URL
    name = "api:shelly:remote"
    requires_auth = False

    def __init__(self, manager: RemoteConnectionManager) -> None:
        """Initialize the remote receiver."""
        self.manager = manager

    async def get(self, request: web.Request) -> web.StreamResponse:
        """Authenticate before upgrading; never expose a credential in an error."""
        if not request.secure or request.headers.get("Origin"):
            return web.Response(status=HTTPStatus.FORBIDDEN)
        record = self.manager.lookup(request.query.get("remote_key", ""))
        if record is None:
            # Raising HTTPUnauthorized invokes HA's login logger, including the URL.
            return web.Response(status=HTTPStatus.UNAUTHORIZED)
        return await self.manager.accept(request, record)


@singleton.singleton("shelly_remote_connection_manager")
async def async_get_remote_manager(hass: HomeAssistant) -> RemoteConnectionManager:
    """Get the remote manager, restoring credentials before entry setup attempts."""
    manager = RemoteConnectionManager(hass)
    for entry in hass.config_entries.async_entries(DOMAIN):
        if is_remote_entry(entry):
            manager.register_entry(entry)
    hass.http.register_view(ShellyRemoteReceiver(manager))

    async def shutdown(_event: Event) -> None:
        for digest in tuple(manager.credentials):
            await manager.revoke(digest)
        manager.server.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)
    return manager
