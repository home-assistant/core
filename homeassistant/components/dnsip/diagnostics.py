"""Diagnostics support for DNS IP."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import ATTR_FRIENDLY_NAME, CONF_NAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import DnsIPConfigEntry
from .const import CONF_HOSTNAME

# The hostname can be the user's own domain and the IPs are often their public IP.
TO_REDACT = {CONF_HOSTNAME, CONF_NAME, ATTR_FRIENDLY_NAME, "ip_addresses"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DnsIPConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entity_registry = er.async_get(hass)
    sensors = [
        {
            "available": state.state != STATE_UNAVAILABLE,
            "attributes": async_redact_data(state.attributes, TO_REDACT),
        }
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
        if (state := hass.states.get(entity_entry.entity_id))
    ]
    return {
        "data": async_redact_data(entry.data, TO_REDACT),
        "options": dict(entry.options),
        "sensors": sensors,
    }
