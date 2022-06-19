"""UniFi Protect Integration utils."""
from __future__ import annotations

from collections.abc import Generator, Iterable
import contextlib
from enum import Enum
import socket
from typing import Any

from pyunifiprotect.data import (
    Bootstrap,
    ProtectAdoptableDeviceModel,
    ProtectDeviceModel,
)

from homeassistant.core import HomeAssistant, callback

from .const import DEVICES_THAT_ADOPT, ModelType


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
def async_device_by_id(
    bootstrap: Bootstrap,
    device_id: str,
    device_type: ModelType | None = None,
) -> ProtectAdoptableDeviceModel | None:
    """Get devices by type."""

    device_types = DEVICES_THAT_ADOPT
    if device_type is not None:
        device_types = {device_type}

    device = None
    for model in device_types:
        device = async_get_devices_by_type(bootstrap, model).get(device_id)
        if device is not None:
            break
    return device


@callback
def async_get_devices(
    bootstrap: Bootstrap, model_type: Iterable[ModelType]
) -> Generator[ProtectDeviceModel, None, None]:
    """Return all device by type."""
    return (
        device
        for device_type in model_type
        for device in async_get_devices_by_type(bootstrap, device_type).values()
    )
