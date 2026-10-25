"""Configuration matching when a direct panel has no hardware identity."""

from collections.abc import Mapping
from contextlib import suppress
import ipaddress
import os
from typing import Any

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE

from .const import CONF_PANEL_SERIAL
from .visonic_types import DeviceType


def normalize_serial_path(device: str) -> str:
    """Preserve serial transport URLs and normalize local device paths."""
    return device if "://" in device else os.path.normpath(device)


def connection_identity(data: Mapping[str, Any]) -> tuple[str, ...] | None:
    """Return matching data; direct endpoints are not config-entry unique IDs."""
    match data.get(CONF_TYPE):
        case DeviceType.ETHERNET:
            if not (host := data.get(CONF_HOST)) or CONF_PORT not in data:
                return None
            host = host.strip().rstrip(".").lower()
            with suppress(ValueError):
                host = str(ipaddress.ip_address(host.strip("[]")))
            return (DeviceType.ETHERNET, host, str(int(data[CONF_PORT])))
        case DeviceType.SERIAL:
            if not (device := data.get(CONF_DEVICE)):
                return None
            return (DeviceType.SERIAL, normalize_serial_path(device))
        case DeviceType.CLOUD:
            if serial := data.get(CONF_PANEL_SERIAL):
                return (DeviceType.CLOUD, serial.strip().upper())
    return None


def resolved_connection_identity(data: Mapping[str, Any]) -> tuple[str, ...] | None:
    """Resolve serial aliases in an executor while preserving stable device paths."""
    if (
        data.get(CONF_TYPE) == DeviceType.SERIAL
        and CONF_DEVICE in data
        and "://" not in data[CONF_DEVICE]
    ):
        data = dict(data) | {CONF_DEVICE: os.path.realpath(data[CONF_DEVICE])}
    return connection_identity(data)
