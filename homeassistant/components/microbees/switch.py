"""Switch integration microBees."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BEES, CONNECTOR, COORDINATOR, DOMAIN
from .coordinator import MicroBeesEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Config entry."""
    microbees = hass.data[DOMAIN][entry.entry_id][CONNECTOR]
    bees = hass.data[DOMAIN][entry.entry_id][BEES]
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
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
        self.act = act
        self.bee = bee
        self.microbees = microbees
        self._attr_unique_id = f"{self.bee.id}_{self.act.id}"
        self._attr_name = self.act.name + " (" + self.bee.name + ")"
        if self.bee.productID == 46:
            self._attr_icon = "mdi:power-socket-it"
        if self.bee.productID == 38:
            self._attr_icon = "mdi:power-socket-eu"
        super().__init__(coordinator, act, bee)

    @property
    def is_on(self) -> bool:
        """Status of the switch."""
        return self.act.value

    @property
    def available(self) -> bool:
        """Status of the bee."""
        return self.bee.active

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

    @callback
    def _handle_coordinator_update(self) -> None:
        self.act.value = self.updated_act.value
        self.bee.active = self.updated_bee.active
        super()._handle_coordinator_update()
