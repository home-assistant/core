"""Z-Wave JS trigger dispatcher."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger

from .triggers import event, value_updated

TRIGGERS = {
    event.PLATFORM_TYPE: Trigger(
        event.async_validate_trigger_config,
        event.async_attach_trigger,
    ),
    value_updated.PLATFORM_TYPE: Trigger(
        value_updated.async_validate_trigger_config,
        value_updated.async_attach_trigger,
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, Trigger]:
    """Return the triggers for Z-Wave JS."""
    return TRIGGERS
