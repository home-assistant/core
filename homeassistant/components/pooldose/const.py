"""Constants for the Seko Pooldose integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

DOMAIN = "pooldose"
DEFAULT_HOST = "KOMMSPOT"
MANUFACTURER = "SEKO"


def device_info(info: dict | None, unique_id: str) -> DeviceInfo:
    """Return device info dict for Pooldose device."""
    info = info or {}
    api_version = info.get("API_VERSION")
    # Remove trailing slash from API version
    if api_version:
        api_version = api_version[:-1]
    return DeviceInfo(
        identifiers={(DOMAIN, unique_id)},
        manufacturer=MANUFACTURER,
        model=info.get("MODEL") or None,
        model_id=info.get("MODEL_ID") or None,
        name=info.get("NAME") or None,
        serial_number=unique_id,
        sw_version=(
            f"{info.get('SW_VERSION', '')} (FW v{info.get('FW_VERSION')}, API {api_version})"
            if info.get("SW_VERSION") and info.get("FW_VERSION") and api_version
            else None
        ),
        hw_version=info.get("FW_CODE", "") or None,
        connections={(CONNECTION_NETWORK_MAC, str(info["MAC"]))}
        if info.get("MAC")
        else set(),
        configuration_url=(
            f"http://{info['IP']}/index.html" if info.get("IP") else None
        ),
    )
