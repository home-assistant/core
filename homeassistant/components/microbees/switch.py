"""Switch integration microBees."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MicroBeesUpdateCoordinator
from .entity import MicroBeesEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    switches = []
    for bee_id, bee in coordinator.data.bees.items():
        if bee.productID in (25, 26, 27, 35, 38, 46, 63, 64, 65, 86):
            for switch in bee.actuators:
                switches.append(MBSwitch(switch.id, bee_id, coordinator))

    async_add_entities(switches)


class MBSwitch(MicroBeesEntity, SwitchEntity):
    """Representation of a microBees switch."""

    def __init__(
        self, actuator_id: int, bee_id: int, coordinator: MicroBeesUpdateCoordinator
    ) -> None:
        """Initialize the microBees switch."""
        super().__init__(actuator_id, bee_id, coordinator)
        if self.bee.productID == 46:
            self._attr_icon = "mdi:power-socket-it"
        if self.bee.productID == 38:
            self._attr_icon = "mdi:power-socket-eu"

    @property
    def name(self) -> str:
        """Status of the switch."""
        return self.actuator.name

    @property
    def is_on(self) -> bool:
        """Status of the switch."""
        return self.actuator.value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        send_command = await self.coordinator.microbees.sendCommand(self.actuator_id, 1)
        if send_command:
            self.actuator.value = True
            self.async_write_ha_state()
        else:
            raise HomeAssistantError(f"Failed to turn on {self.name}")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        send_command = await self.coordinator.microbees.sendCommand(self.actuator_id, 0)
        if send_command:
            self.actuator.value = False
            self.async_write_ha_state()
        else:
            raise HomeAssistantError(f"Failed to turn off {self.name}")
