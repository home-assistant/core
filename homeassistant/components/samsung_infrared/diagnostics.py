"""Diagnostics support for Samsung Infrared."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_EMITTER_ENTITY_ID


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, str]:
    """Return diagnostics for a config entry."""

    emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    emitter_state = hass.states.get(emitter_entity_id)

    return {
        "infrared_emitter_entity_id": emitter_entity_id,
        "device_type": entry.data[CONF_DEVICE_TYPE],
        "infrared_emitter_state": emitter_state.state if emitter_state else None,
    }
