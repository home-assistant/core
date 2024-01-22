"""Integration microBees."""
import logging
from typing import Any

from homeassistant.components.switch import ToggleEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the microBees switch platform."""
    microbees = hass.data[DOMAIN]["connector"]
    bees = hass.data[DOMAIN]["bees"]
    switches = []
    for bee in bees:
        if bee.active:
            if bee.productID == 46:
                for switch in bee.actuators:
                    switches.append(MBSwitch(switch, microbees))
    async_add_entities(switches)


class MBSwitch(ToggleEntity):
    """Representation of a microBees switch."""

    def __init__(self, act, microbees) -> None:
        """Initialize the microBees switch."""
        self.act = act
        self.microbees = microbees
        self._state = self.act.value

    @property
    def name(self) -> str | None:
        """Return the name of the switch."""
        return self.act.name

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID for the switch."""
        return self.act.id

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        return self.act.value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        sendCommand = await self.microbees.sendCommand(self.act.id, 1)
        if sendCommand:
            self.act.value = 1

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        sendCommand = await self.microbees.sendCommand(self.act.id, 0)
        if sendCommand:
            self.act.value = 0

    async def async_update(self) -> None:
        """Update the switch value."""
        actuator = await self.microbees.getActuatorById(self.act.id)
        if actuator:
            self.act.value = actuator.value
            self._state = self.act.value
