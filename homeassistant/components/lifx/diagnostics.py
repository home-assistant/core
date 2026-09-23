"""Diagnostics support for LIFX."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_LOCATION
from homeassistant.core import HomeAssistant

from .const import CONF_GROUP, CONF_LABEL, CONF_MAC_ADDRESS, CONF_SERIAL, CONF_TITLE
from .coordinator import LIFXConfigEntry

TO_REDACT = [
    CONF_LABEL,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_SERIAL,
    CONF_TITLE,
    CONF_MAC_ADDRESS,
    CONF_GROUP,
    CONF_LOCATION,
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LIFXConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a LIFX config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(
            {CONF_TITLE: entry.title, "data": entry.data}, TO_REDACT
        ),
        "data": async_redact_data(coordinator.data.as_dict, TO_REDACT),
    }
