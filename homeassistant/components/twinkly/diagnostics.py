"""Diagnostics support for Twinkly."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DATA_DEVICE_INFO

TO_REDACT = [CONF_HOST, CONF_IP_ADDRESS, CONF_MAC]
DOMAIN = "light"
PLATFORM = "twinkly"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Twinkly config entry."""
    attributes = None
    state = None
    entity_registry = er.async_get(hass)

    entity_id = entity_registry.async_get_entity_id(
        DOMAIN, PLATFORM, str(entry.unique_id)
    )
    if entity_id:
        state = hass.states.get(entity_id)
    if state:
        attributes = state.attributes
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_info": async_redact_data(
            hass.data[PLATFORM][entry.entry_id][DATA_DEVICE_INFO], TO_REDACT
        ),
        "attributes": async_redact_data(attributes, TO_REDACT),
    }
