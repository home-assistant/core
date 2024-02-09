"""Switch integration microBees."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MicroBeesEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Config entry."""
    microbees_data = hass.data[DOMAIN][entry.entry_id]
    microbees = microbees_data.connector
    bees = microbees_data.bees
    coordinator = microbees_data.coordinator
    switches = []
    for bee in bees:
        match bee.productID:
            case 25 | 26 | 27 | 35 | 38 | 46 | 63 | 64 | 65 | 86:
                for switch in bee.actuators:
                    switches.append(MBSwitch(switch, bee, microbees, coordinator))

    async_add_entities(switches)


class MBSwitch(MicroBeesEntity, SwitchEntity):
    """Representation of a microBees switch."""

    def __init__(self, act, bee, microbees, coordinator) -> None:
        """Initialize the microBees switch."""
        super().__init__(coordinator, act, bee, microbees)
        if self.bee.productID == 46:
            self._attr_icon = "mdi:power-socket-it"
        if self.bee.productID == 38:
            self._attr_icon = "mdi:power-socket-eu"

    @property
    def is_on(self) -> bool:
        """Status of the switch."""
        return self.act.value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        sendCommand = await self.microbees.sendCommand(self.act.id, 1)
        if sendCommand:
            self.act.value = True
            self.async_write_ha_state()
        else:
            raise HomeAssistantError(f"Failed to turn on {self.name}")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        sendCommand = await self.microbees.sendCommand(self.act.id, 0)
        if sendCommand:
            self.act.value = False
            self.async_write_ha_state()
        else:
            raise HomeAssistantError(f"Failed to turn off {self.name}")
