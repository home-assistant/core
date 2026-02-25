"""Rain Bird integration API helpers."""

from __future__ import annotations

import aiohttp
from pyrainbird.async_client import AsyncRainbirdController, create_controller
from yarl import URL


def normalize_rainbird_host(host: str) -> str:
    """Normalize a controller host value to a hostname[:port] string.

    The `pyrainbird.create_controller` factory expects a hostname/IP address
    (optionally with a port) and will probe the controller using both HTTPS and
    HTTP. Users may provide a URL (for example, `https://<host>`), so strip any
    scheme and path components to avoid constructing invalid endpoints like
    `https://https://<host>/stick`.
    """
    host = host.strip()
    if not host:
        return host

    if host.startswith(("http://", "https://")):
        url = URL(host)
        if (normalized_host := url.host) is not None:
            if ":" in normalized_host and not normalized_host.startswith("["):
                normalized_host = f"[{normalized_host}]"
            if url.explicit_port is not None:
                return f"{normalized_host}:{url.explicit_port}"
            return normalized_host

    host = host.split("?", 1)[0].split("#", 1)[0]
    host = host.rstrip("/")
    return host.split("/", 1)[0]


async def async_create_controller(
    clientsession: aiohttp.ClientSession,
    host: str,
    password: str,
) -> AsyncRainbirdController:
    """Create a pyrainbird controller."""
    return await create_controller(
        clientsession, normalize_rainbird_host(host), password
    )
