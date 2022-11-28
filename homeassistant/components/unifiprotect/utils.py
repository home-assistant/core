"""UniFi Protect Integration utils."""
from __future__ import annotations

import contextlib
from enum import Enum
import re
import socket
from typing import Any

from pyunifiprotect.data import (
    Bootstrap,
    Light,
    LightModeEnableType,
    LightModeType,
    ProtectAdoptableDeviceModel,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, ModelType

MAC_RE = re.compile(r"[0-9A-F]{12}")


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
def async_unifi_mac(mac: str) -> str:
    """Convert MAC address to format from UniFi Protect."""
    # MAC addresses in UFP are always caps
    return mac.replace(":", "").replace("-", "").replace("_", "").upper()


@callback
def async_short_mac(mac: str) -> str:
    """Get the short mac address from the full mac."""
    return async_unifi_mac(mac)[-6:]


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


@callback
def async_get_devices_by_type(
    bootstrap: Bootstrap, device_type: ModelType
) -> dict[str, ProtectAdoptableDeviceModel]:
    """Get devices by type."""

    devices: dict[str, ProtectAdoptableDeviceModel] = getattr(
        bootstrap, f"{device_type.value}s"
    )
    return devices


@callback
def async_get_light_motion_current(obj: Light) -> str:
    """Get light motion mode for Flood Light."""

    if (
        obj.light_mode_settings.mode == LightModeType.MOTION
        and obj.light_mode_settings.enable_at == LightModeEnableType.DARK
    ):
        return f"{LightModeType.MOTION.value}Dark"
    return obj.light_mode_settings.mode.value


@callback
def async_dispatch_id(entry: ConfigEntry, dispatch: str) -> str:
    """Generate entry specific dispatch ID."""

    return f"{DOMAIN}.{entry.entry_id}.{dispatch}"


@callback
def convert_mac_list(option: str, raise_exception: bool = False) -> set[str]:
    """Convert csv list of MAC addresses."""

    macs = set()
    values = cv.ensure_list_csv(option)
    for value in values:
        if value == "":
            continue
        value = async_unifi_mac(value)
        if not MAC_RE.match(value):
            if raise_exception:
                raise vol.Invalid("invalid_mac_list")
            continue
        macs.add(value)

    return macs
