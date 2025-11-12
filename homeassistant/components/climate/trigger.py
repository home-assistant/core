"""Provides triggers for climates."""

from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import EntityStateTriggerBase, Trigger, TriggerConfig

from .const import DOMAIN


class TurnedOffTrigger(EntityStateTriggerBase):
    """Trigger for when a climate is turned off."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the OFF state trigger."""
        super().__init__(hass, config, STATE_OFF)


TRIGGERS: dict[str, type[Trigger]] = {
    "turned_off": TurnedOffTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for climates."""
    return TRIGGERS
