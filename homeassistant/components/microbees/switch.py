"""Switch integration microBees."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MicroBeesUpdateCoordinator
from .entity import MicroBeesActuatorEntity

SOCKET_TRANSLATIONS = {46: "socket_it", 38: "socket_eu"}
SWITCH_PRODUCT_IDS = {25, 26, 27, 35, 38, 46, 63, 64, 65, 86}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id].coordinator

    async_add_entities(
        MBSwitch(coordinator, bee_id, switch.id)
        for bee_id, bee in coordinator.data.bees.items()
        if bee.productID in SWITCH_PRODUCT_IDS
        for switch in bee.actuators
    )


class MBSwitch(MicroBeesActuatorEntity, SwitchEntity):
    """Representation of a microBees switch."""

    def __init__(
        self,
        coordinator: MicroBeesUpdateCoordinator,
        bee_id: int,
        actuator_id: int,
    ) -> None:
        """Initialize the microBees switch."""
        super().__init__(coordinator, bee_id, actuator_id)
        self._attr_translation_key = SOCKET_TRANSLATIONS.get(self.bee.productID)

    @property
    def name(self) -> str:
        """Name of the switch."""
        return self.actuator.name

    @property
    def is_on(self) -> bool:
        """Status of the switch."""
        return self.actuator.value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        send_command = await self.coordinator.microbees.sendCommand(self.actuator_id, 1)
        if not send_command:
            raise HomeAssistantError(f"Failed to turn on {self.name}")

        self.actuator.value = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        send_command = await self.coordinator.microbees.sendCommand(self.actuator_id, 0)
        if not send_command:
            raise HomeAssistantError(f"Failed to turn off {self.name}")

        self.actuator.value = False
        self.async_write_ha_state()
