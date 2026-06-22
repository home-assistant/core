"""Light entity for the SystemNexa2 integration."""

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SystemNexa2ConfigEntry, SystemNexa2DataUpdateCoordinator
from .entity import SystemNexa2Entity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SystemNexa2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lights based on a config entry."""
    coordinator = entry.runtime_data

    # Only add light entity for dimmable devices
    if coordinator.data.info_data.dimmable:
        async_add_entities([SystemNexa2Light(coordinator)])


class SystemNexa2Light(SystemNexa2Entity, LightEntity):
    """Representation of a dimmable SystemNexa2 light."""

    _attr_translation_key = "light"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        coordinator: SystemNexa2DataUpdateCoordinator,
    ) -> None:
        """Initialize the light."""
        super().__init__(
            coordinator=coordinator,
            key="light",
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        # Check if we're setting brightness
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            # Convert HomeAssistant brightness (0-255) to device brightness (0-1.0)
            value = brightness / 255
            await self.coordinator.async_set_brightness(value)
        else:
            await self.coordinator.async_turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.coordinator.async_turn_off()

    @property
    def is_on(self) -> bool | None:
        """Return true if the light is on."""
        if self.coordinator.data.state is None:
            return None
        # Consider the light on if brightness is greater than 0
        return self.coordinator.data.state > 0

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light (0-255)."""
        if self.coordinator.data.state is None:
            return None
        # Convert device brightness (0-1.0) to HomeAssistant brightness (0-255)
        return max(0, min(255, round(self.coordinator.data.state * 255)))
