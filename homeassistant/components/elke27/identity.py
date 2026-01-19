"""Identity helpers for the Elke27 integration."""

from __future__ import annotations

import secrets
import socket
from typing import Any

import psutil_home_assistant as ha_psutil

from homeassistant.components import network
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac

from .const import INTEGRATION_SERIAL_LENGTH, MANUFACTURER_NUMBER


async def async_get_integration_serial(
    hass: HomeAssistant, host: str, existing: str | None = None
) -> str:
    """Return the persisted integration serial, generating one if needed."""
    if existing:
        return existing

    target_ip = await hass.async_add_executor_job(_resolve_host, host)
    try:
        source_ip = await network.async_get_source_ip(hass, target_ip=target_ip)
    except (HomeAssistantError, OSError):
        return _generate_serial_number()
    if not source_ip:
        return _generate_serial_number()
    mac = await hass.async_add_executor_job(_get_mac_for_source_ip, source_ip)
    if mac:
        return _normalize_serial(mac)
    return _generate_serial_number()


def _resolve_host(host: str) -> str:
    try:
        return socket.gethostbyname(host)
    except OSError:
        return host


def _get_mac_for_source_ip(source_ip: str) -> str | None:
    try:
        psutil_wrapper = ha_psutil.PsutilWrapper()
        addresses = psutil_wrapper.psutil.net_if_addrs()
    except (OSError, RuntimeError):
        return None

    for addrs in addresses.values():
        if not any(addr.address == source_ip for addr in addrs):
            continue
        mac = _extract_mac(addrs)
        if mac:
            return mac
    return None


def _extract_mac(addrs: list[Any]) -> str | None:
    mac_families = {
        getattr(socket, "AF_PACKET", None),
        getattr(socket, "AF_LINK", None),
    }
    for addr in addrs:
        if addr.family in mac_families and addr.address:
            return format_mac(addr.address)
    return None


def _generate_serial_number() -> str:
    return "".join(
        secrets.choice("0123456789") for _ in range(INTEGRATION_SERIAL_LENGTH)
    )


def _normalize_serial(serial: str) -> str:
    """Return a digits-only serial string for provisioning."""
    return "".join(ch for ch in serial if ch.isalnum()).lower()


def build_client_identity(integration_serial: str) -> dict[str, str]:
    """Return the client identity mapping for provisioning and session setup."""
    return {
        "mn": str(MANUFACTURER_NUMBER),
        "sn": integration_serial,
    }
