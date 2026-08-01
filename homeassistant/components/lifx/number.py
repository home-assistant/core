"""Number entities for LIFX lights."""

from typing import override

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import INFRARED_BRIGHTNESS
from .coordinator import LIFXConfigEntry, LIFXUpdateCoordinator
from .entity import LIFXEntity

PARALLEL_UPDATES = 1

INFRARED_BRIGHTNESS_ENTITY = NumberEntityDescription(
    key=INFRARED_BRIGHTNESS,
    translation_key="infrared_brightness",
    entity_category=EntityCategory.CONFIG,
    native_min_value=0,
    native_max_value=100,
    native_step=1,
    native_unit_of_measurement=PERCENTAGE,
    mode=NumberMode.SLIDER,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LIFXConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LIFX numbers from a config entry."""
    coordinator = entry.runtime_data
    if coordinator.data.capabilities.has_infrared:
        async_add_entities(
            [LIFXInfraredBrightnessNumber(coordinator, INFRARED_BRIGHTNESS_ENTITY)]
        )


class LIFXInfraredBrightnessNumber(LIFXEntity, NumberEntity):
    """LIFX Nightvision infrared brightness configuration entity."""

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        description: NumberEntityDescription,
    ) -> None:
        """Initialise the infrared brightness entity."""
        super().__init__(coordinator, description)
        self._async_update_attrs()

    @callback
    @override
    def _async_update_attrs(self) -> None:
        """Handle coordinator updates."""
        self._attr_native_value = self.coordinator.infrared_brightness

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the infrared brightness."""
        await self.coordinator.async_set_infrared_brightness(value)
