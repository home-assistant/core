"""Button integration microBees."""
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MicroBeesUpdateCoordinator
from .entity import MicroBeesActuatorEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the microBees button platform."""
    coordinator: MicroBeesUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ].coordinator
    async_add_entities(
        [
            MBButton(coordinator, bee_id, button.id)
            for bee_id, bee in coordinator.data.bees.items()
            if bee.productID == 51
            for button in bee.actuators
        ]
    )


class MBButton(MicroBeesActuatorEntity, ButtonEntity):
    """Representation of a microBees button."""

    def __init__(
        self,
        coordinator: MicroBeesUpdateCoordinator,
        bee_id: int,
        actuator_id: int,
    ) -> None:
        """Initialize the microBees button."""
        super().__init__(coordinator, bee_id, actuator_id)
        self._attr_icon = "mdi:gate"

    @property
    def name(self) -> str:
        """Name of the switch."""
        return self.actuator.name

    async def async_press(self, **kwargs: Any) -> None:
        """Turn on the button."""
        await self.coordinator.microbees.sendCommand(
            self.actuator.id, self.actuator.configuration.actuator_timing * 1000
        )
