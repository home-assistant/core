"""Z-Wave JS trigger dispatcher."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger
from homeassistant.util.decorator import Registry

TRIGGERS: Registry[str, type[Trigger]] = Registry()


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for Z-Wave JS."""
    return TRIGGERS
