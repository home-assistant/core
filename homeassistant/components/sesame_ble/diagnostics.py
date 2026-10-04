"""Diagnostics support for the Candy House Sesame BLE integration."""

from typing import TYPE_CHECKING, Any

from homeassistant.components import bluetooth
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_UUID, CONF_SECRET_KEY

if TYPE_CHECKING:
    from . import SesameBleConfigEntry

TO_REDACT = {
    CONF_SECRET_KEY,
    "mac_address",
    CONF_DEVICE_UUID,
    "unique_id",
    "title",
    "discovery_keys",
}
TO_REDACT_BLUETOOTH = {"address", "device", "manufacturer_data", "source"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SesameBleConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    wrapper = getattr(entry, "runtime_data", None)

    service_info = None
    runtime: dict[str, Any] = {}

    if wrapper is not None:
        service_info = bluetooth.async_last_service_info(hass, wrapper.mac_address)
        device = wrapper.device
        runtime = {
            "model": wrapper.model_name,
            "connected": getattr(device, "is_connected", None),
            "authenticated": getattr(device, "is_logged_in", None),
            "firmware_version": wrapper.fw_version,
        }

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "bluetooth": (
            async_redact_data(service_info.as_dict(), TO_REDACT_BLUETOOTH)
            if service_info
            else None
        ),
        "runtime": runtime,
    }
