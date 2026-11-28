"""Stable, user-facing identity helpers for reCamera Pro."""

from collections.abc import Mapping
from typing import Any

from recamera_protocol import (
    RecameraDeviceInfo,
    normalize_mac_address,
    normalize_serial_number,
)

from homeassistant.const import CONF_HOST

from .const import CONF_DISCOVERY_ID, CONF_MAC_ADDRESS, CONF_SERIAL_NUMBER


def device_identity(serial_number: object, mac_address: object) -> str | None:
    """Return the product serial number, falling back to a normalized MAC."""
    if serial := normalize_serial_number(serial_number):
        return serial
    if mac := normalize_mac_address(mac_address):
        return mac.upper()
    return None


def device_title(
    serial_number: object,
    mac_address: object,
    *,
    fallback: str | None = None,
) -> str:
    """Build the canonical Home Assistant device title."""
    identity = device_identity(serial_number, mac_address)
    if identity is None:
        identity = str(fallback or "").strip()
    return f"reCamera Pro ({identity})" if identity else "reCamera Pro"


def probe_identity_mismatch(
    data: Mapping[str, Any],
    unique_id: str | None,
    info: RecameraDeviceInfo,
) -> bool:
    """Return whether authenticated device metadata differs from an entry."""
    serial_number = info.serial_number
    stored_serial = normalize_serial_number(data.get(CONF_SERIAL_NUMBER))
    stored_mac = normalize_mac_address(data.get(CONF_MAC_ADDRESS))
    if stored_serial:
        if serial_number:
            if serial_number != stored_serial:
                return True
        elif not (stored_mac and info.mac_address and stored_mac == info.mac_address):
            return True
    if stored_mac and not info.mac_address:
        return True
    if stored_mac and info.mac_address:
        return stored_mac != info.mac_address
    if not serial_number:
        return False

    advertised_id = str(data.get(CONF_DISCOVERY_ID) or unique_id or "").strip()
    configured_host = str(data.get(CONF_HOST) or "").strip()
    if not advertised_id or advertised_id == configured_host:
        return False
    return serial_number != advertised_id
