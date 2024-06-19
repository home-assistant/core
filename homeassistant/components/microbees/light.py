"""Light integration microBees."""

from typing import Any

from homeassistant.components.light import ATTR_RGBW_COLOR, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MicroBeesUpdateCoordinator
from .entity import MicroBeesActuatorEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Config entry."""
    coordinator: MicroBeesUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ].coordinator
    async_add_entities(
        MBLight(coordinator, bee_id, light.id)
        for bee_id, bee in coordinator.data.bees.items()
        if bee.productID in (31, 79)
        for light in bee.actuators
    )


class MBLight(MicroBeesActuatorEntity, LightEntity):
    """Representation of a microBees light."""

    _attr_supported_color_modes = {ColorMode.RGBW}

    def __init__(
        self,
        coordinator: MicroBeesUpdateCoordinator,
        bee_id: int,
        actuator_id: int,
    ) -> None:
        """Initialize the microBees light."""
        super().__init__(coordinator, bee_id, actuator_id)
        self._attr_rgbw_color = self.actuator.configuration.color

    @property
    def name(self) -> str:
        """Name of the cover."""
        return self.actuator.name

    @property
    def is_on(self) -> bool:
        """Status of the light."""
        return self.actuator.value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        if ATTR_RGBW_COLOR in kwargs:
            self._attr_rgbw_color = kwargs[ATTR_RGBW_COLOR]
        sendCommand = await self.coordinator.microbees.sendCommand(
            self.actuator_id, 1, color=self._attr_rgbw_color
        )
        if not sendCommand:
            raise HomeAssistantError(f"Failed to turn on {self.name}")

        self.actuator.value = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        sendCommand = await self.coordinator.microbees.sendCommand(
            self.actuator_id, 0, color=self._attr_rgbw_color
        )
        if not sendCommand:
            raise HomeAssistantError(f"Failed to turn off {self.name}")

        self.actuator.value = False
        self.async_write_ha_state()
