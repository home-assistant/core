"""iTach UDP discovery hardware layer.

This private module owns the Global Caché/iTach UDP discovery transport and
beacon parsing. It intentionally contains no Home Assistant imports or config
entry logic. Public consumers should import discovery helpers from the
integration's ``pyitach`` package rather than this private module.
"""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
import logging
import re
import socket
import struct
from typing import Final
from urllib.parse import urlparse

_LOGGER = logging.getLogger(__name__)

_MULTICAST_GROUP: Final = "239.255.250.250"
_DISCOVERY_PORT: Final = 9131
_BUFFER_SIZE: Final = 2048

_UUID_RE: Final = re.compile(r"<-UUID=([^>]+)>", re.IGNORECASE)
_MODEL_RE: Final = re.compile(r"<-Model=([^>]+)>", re.IGNORECASE)
_CONFIG_URL_RE: Final = re.compile(
    r"<-Config-URL=([^>]+)>",
    re.IGNORECASE,
)
_CANONICAL_UUID_RE: Final = re.compile(
    r"^GlobalCache_([0-9A-Fa-f]{12})$",
    re.IGNORECASE,
)
_RAW_ID_RE: Final = re.compile(r"^[0-9A-Fa-f]{12}$")
_INVALID_CONFIG_URL_SCHEME: Final = object()


@dataclass(frozen=True, slots=True)
class ItachDiscoveryBeacon:
    """Parsed Global Caché discovery beacon."""

    host: str
    uuid: str
    model: str


def normalize_host(host: str | None) -> str | None:
    """Normalize a discovered host value."""
    if host is None:
        return None

    normalized = host.strip().rstrip(".").lower()
    return normalized or None


def _host_from_config_url(config_url: str | None) -> str | object | None:
    """Return normalized host from a discovery Config-URL value.

    Unsupported explicit URL schemes are treated differently from malformed or
    hostless URLs: unsupported schemes reject the beacon, while malformed or
    hostless URLs can fall back to the packet source host.
    """
    if config_url is None:
        return None

    cleaned_url = config_url.strip()
    if not cleaned_url:
        return None

    if "://" not in cleaned_url:
        cleaned_url = f"http://{cleaned_url}"

    try:
        parsed = urlparse(cleaned_url)
        parsed_scheme = parsed.scheme.lower()
        parsed_hostname = parsed.hostname
    except ValueError:
        return None

    if parsed_scheme not in {"http", "https"}:
        return _INVALID_CONFIG_URL_SCHEME

    return normalize_host(parsed_hostname)


def normalize_uuid(uuid: str | None) -> str | None:
    """Normalize Global Caché UUID to GlobalCache_XXXXXXXXXXXX."""
    if uuid is None:
        return None

    cleaned = uuid.strip()

    canonical_match = _CANONICAL_UUID_RE.match(cleaned)
    if canonical_match:
        return f"GlobalCache_{canonical_match.group(1).upper()}"

    raw_id = cleaned.replace(":", "").replace("-", "").replace(" ", "").upper()

    if _RAW_ID_RE.match(raw_id) and raw_id != "000000000000":
        return f"GlobalCache_{raw_id}"

    return None


def parse_discovery_beacon(
    message: str,
    packet_host: str | None = None,
) -> ItachDiscoveryBeacon | None:
    """Parse a Global Caché UDP discovery beacon."""
    message_lower = message.lower()
    if "amxb" not in message_lower or "globalcache" not in message_lower:
        return None

    uuid_match = _UUID_RE.search(message)
    model_match = _MODEL_RE.search(message)
    config_url_match = _CONFIG_URL_RE.search(message)

    uuid = normalize_uuid(uuid_match.group(1)) if uuid_match else None
    model = model_match.group(1).strip() if model_match else None
    config_host = (
        _host_from_config_url(config_url_match.group(1)) if config_url_match else None
    )
    if config_host is _INVALID_CONFIG_URL_SCHEME:
        return None

    host = str(config_host) if config_host else normalize_host(packet_host)

    if host is None or uuid is None or model is None:
        return None

    return ItachDiscoveryBeacon(host=host, uuid=uuid, model=model)


def _create_multicast_socket() -> socket.socket:
    """Create and configure a UDP multicast discovery socket."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        with suppress(AttributeError, OSError):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        sock.bind(("", _DISCOVERY_PORT))

        mreq = struct.pack(
            "4s4s",
            socket.inet_aton(_MULTICAST_GROUP),
            socket.inet_aton("0.0.0.0"),
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.setblocking(False)
    except Exception:
        sock.close()
        raise

    return sock


async def async_discover_once(timeout: float = 5.0) -> ItachDiscoveryBeacon | None:
    """Listen briefly for a single Global Caché discovery beacon."""
    _LOGGER.debug("Starting temporary iTach discovery timeout=%s", timeout)

    try:
        sock = _create_multicast_socket()
    except OSError as err:
        _LOGGER.debug("Temporary iTach discovery failed: %s", err)
        return None

    try:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout

        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return None

            try:
                data, addr = await asyncio.wait_for(
                    loop.sock_recvfrom(sock, _BUFFER_SIZE),
                    timeout=remaining,
                )
            except TimeoutError:
                return None

            packet_host = normalize_host(addr[0])
            message = data.decode("utf-8", errors="replace")
            parsed = parse_discovery_beacon(message, packet_host)

            if parsed is not None:
                return parsed

    finally:
        with suppress(OSError):
            sock.close()


class ItachDiscoveryListener:
    """Async UDP multicast listener for Global Caché discovery beacons."""

    def __init__(
        self,
        on_beacon: Callable[[ItachDiscoveryBeacon], Awaitable[None]],
    ) -> None:
        """Initialize the listener."""
        self._on_beacon = on_beacon
        self._sock: socket.socket | None = None
        self._task: asyncio.Task[None] | None = None

    async def async_start(self) -> bool:
        """Start listening for discovery beacons."""
        if self._task is not None:
            return True

        try:
            sock = _create_multicast_socket()
        except OSError as err:
            _LOGGER.warning("Failed to start iTach discovery socket: %s", err)
            return False

        self._sock = sock
        self._task = asyncio.create_task(self._listen_loop())
        return True

    async def async_stop(self) -> None:
        """Stop listening for discovery beacons."""
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        if self._sock is not None:
            with suppress(OSError):
                self._sock.close()
            self._sock = None

    async def _listen_loop(self) -> None:
        """Receive multicast beacons and dispatch parsed results."""
        assert self._sock is not None
        loop = asyncio.get_running_loop()

        while True:
            try:
                data, addr = await loop.sock_recvfrom(self._sock, _BUFFER_SIZE)
            except asyncio.CancelledError:
                raise
            except OSError as err:
                _LOGGER.debug("iTach discovery socket receive failed: %s", err)
                await asyncio.sleep(1)
                continue

            packet_host = normalize_host(addr[0])
            message = data.decode("utf-8", errors="replace")
            parsed = parse_discovery_beacon(message, packet_host)

            if parsed is not None:
                try:
                    await self._on_beacon(parsed)
                except Exception:
                    _LOGGER.exception("Error handling iTach discovery beacon")
