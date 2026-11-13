"""Diagnostics support for Daikin."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PASSWORD, CONF_UUID
from homeassistant.core import HomeAssistant

from .const import KEY_MAC
from .coordinator import DaikinConfigEntry

TO_REDACT_ENTRY = {CONF_API_KEY, CONF_HOST, CONF_PASSWORD, CONF_UUID, KEY_MAC}
TO_REDACT_DEVICE = {"mac"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DaikinConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device = entry.runtime_data.device
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT_ENTRY),
        "device": {
            "values": async_redact_data(dict(device.values), TO_REDACT_DEVICE),
            "support_away_mode": device.support_away_mode,
            "support_advanced_modes": device.support_advanced_modes,
            "support_fan_rate": device.support_fan_rate,
            "support_swing_mode": device.support_swing_mode,
            "support_outside_temperature": device.support_outside_temperature,
            "support_humidity": device.support_humidity,
            "support_energy_consumption": device.support_energy_consumption,
            "support_compressor_frequency": device.support_compressor_frequency,
        },
    }
