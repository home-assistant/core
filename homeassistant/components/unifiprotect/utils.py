"""UniFi Protect Integration utils."""
from __future__ import annotations

import contextlib
from enum import Enum
import socket
from typing import Any

from homeassistant.core import HomeAssistant, callback


def get_nested_attr(obj: Any, attr: str) -> Any:
    """Fetch a nested attribute."""
    attrs = attr.split(".")

    value = obj
    for key in attrs:
        if not hasattr(value, key):
            return None
        value = getattr(value, key)

    if isinstance(value, Enum):
        value = value.value

    return value


@callback
def _async_unifi_mac_from_hass(mac: str) -> str:
    # MAC addresses in UFP are always caps
    return mac.replace(":", "").upper()


@callback
def _async_short_mac(mac: str) -> str:
    """Get the short mac address from the full mac."""
    return _async_unifi_mac_from_hass(mac)[-6:]


async def _async_resolve(hass: HomeAssistant, host: str) -> str | None:
    """Resolve a hostname to an ip."""
    with contextlib.suppress(OSError):
        return next(
            iter(
                raw[0]
                for family, _, _, _, raw in await hass.loop.getaddrinfo(
                    host, None, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
                )
                if family == socket.AF_INET
            ),
            None,
        )
    return None
