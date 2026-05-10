"""Helpers for UniFi Network config entry unique IDs."""

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac

UNIQUE_ID_SEPARATOR = "::"


@callback
def controller_key_from_system_info(system_info: Any) -> str | None:
    """Return a stable controller key from UniFi system information."""
    raw = getattr(system_info, "raw", {})

    for key in ("mac", "mac_address", "device_mac"):
        if mac := raw.get(key):
            return format_mac(str(mac))

    if anonymous_controller_id := getattr(system_info, "anonymous_controller_id", None):
        return str(anonymous_controller_id).strip().lower()

    return None


@callback
def make_unique_id(controller_key: str, site_id: str) -> str:
    """Build a config-entry unique ID for one controller and one site."""
    return f"{controller_key}{UNIQUE_ID_SEPARATOR}{site_id}"


@callback
def extract_site_id(unique_id: str | None) -> str | None:
    """Return the raw site_id from a legacy or compound unique ID."""
    if not unique_id:
        return None
    if UNIQUE_ID_SEPARATOR not in unique_id:
        return unique_id
    return unique_id.rsplit(UNIQUE_ID_SEPARATOR, 1)[-1]


@callback
def extract_controller_key(unique_id: str | None) -> str | None:
    """Return the controller key from a compound unique ID if present."""
    if not unique_id or UNIQUE_ID_SEPARATOR not in unique_id:
        return None
    return unique_id.split(UNIQUE_ID_SEPARATOR, 1)[0]
