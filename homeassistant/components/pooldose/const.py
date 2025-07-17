"""Constants for Pooldose integration.

All entity maps include an 'enabled_by_default' boolean as last tuple value.
This controls if the entity is enabled by default in the entity registry.
"""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

DOMAIN = "pooldose"

DEFAULT_HOST = "KOMMSPOT"  # Default host for PoolDose device, used in config flow

CONF_SERIALNUMBER = "serialnumber"

MANUFACTURER = "SEKO"


def device_info(info: dict | None) -> DeviceInfo:
    """Return device info dict for Pooldose device."""
    info = info or {}
    serial_number = info.get("SERIAL_NUMBER") or "no_serial_number"
    api_version = info.get("API_VERSION")
    # Remove trailing slash from API version
    if api_version:
        api_version = api_version[:-1]
    return DeviceInfo(
        identifiers={(DOMAIN, serial_number)},
        manufacturer=MANUFACTURER,
        model=info.get("MODEL") or None,
        model_id=info.get("MODEL_ID") or None,
        name=info.get("NAME") or None,
        serial_number=serial_number,
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
