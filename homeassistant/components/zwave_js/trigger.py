"""Z-Wave JS trigger dispatcher."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger

from .triggers import event, node_status, value_updated

TRIGGERS = {
    event.RELATIVE_PLATFORM_TYPE: event.EventTrigger,
    node_status.RELATIVE_PLATFORM_TYPE: node_status.NodeStatusTrigger,
    value_updated.RELATIVE_PLATFORM_TYPE: value_updated.ValueUpdatedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for Z-Wave JS."""
    return TRIGGERS
