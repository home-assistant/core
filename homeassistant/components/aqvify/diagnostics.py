"""Diagnostics platform for Aqvify integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .coordinator import AqvifyConfigEntry

TO_REDACT = [CONF_API_KEY]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AqvifyConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    device_list_raw_data = entry.runtime_data.data.devices.raw
    device_data_raw_data = {
        key: device.raw_data
        for key, device in entry.runtime_data.data.device_data.items()
    }

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "devices": async_redact_data(device_list_raw_data, ["name"]),
        "device_data": device_data_raw_data,
    }
