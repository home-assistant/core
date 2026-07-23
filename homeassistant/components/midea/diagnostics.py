"""Midea diagnostic."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from .const import CONF_KEY
from .entity import MideaConfigEntry

TO_REDACT = {CONF_TOKEN, CONF_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MideaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    device = entry.runtime_data

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_attributes": device.attributes,
    }
