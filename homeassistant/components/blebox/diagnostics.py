"""Diagnostics support for BleBox devices."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import BleBoxConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BleBoxConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    product = entry.runtime_data.box

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device": {
            "name": product.name,
            "type": product.type,
            "model": product.model,
            "unique_id": product.unique_id,
            "firmware_version": product.firmware_version,
            "hardware_version": product.hardware_version,
            "available_firmware_version": product.available_firmware_version,
            "api_version": product.api_version,
            "last_data": product.last_data,
        },
    }
