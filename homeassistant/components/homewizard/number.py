"""Creates HomeWizard Number entities."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeWizardConfigEntry
from .coordinator import HWEnergyDeviceUpdateCoordinator
from .entity import HomeWizardEntity
from .helpers import homewizard_exception_handler

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeWizardConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up numbers for device."""
    if entry.runtime_data.data.device.supports_state():
        async_add_entities([HWEnergyNumberEntity(entry.runtime_data)])


class HWEnergyNumberEntity(HomeWizardEntity, NumberEntity):
    """Representation of status light number."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "status_light_brightness"
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
    ) -> None:
        """Initialize the control number."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_status_light_brightness"
        )

    @homewizard_exception_handler
    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        await self.coordinator.api.system(status_led_brightness_pct=int(value))
        await self.coordinator.async_refresh()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.data.system is not None

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if (
            not self.coordinator.data.system
            or (brightness := self.coordinator.data.system.status_led_brightness_pct)
            is None
        ):
            return None
        return round(brightness)
