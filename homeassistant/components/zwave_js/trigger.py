"""Z-Wave JS trigger dispatcher."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger

from .triggers import event, value_updated

TRIGGERS = {
    event.RELATIVE_PLATFORM_TYPE: event.EventTrigger,
    value_updated.RELATIVE_PLATFORM_TYPE: value_updated.ValueUpdatedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for Z-Wave JS."""
    return TRIGGERS
