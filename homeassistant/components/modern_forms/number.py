"""Support for Modern Forms numbers."""

from typing import override

from homeassistant.components.number import NumberEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import modernforms_exception_handler
from .coordinator import ModernFormsConfigEntry, ModernFormsDataUpdateCoordinator
from .entity import ModernFormsDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ModernFormsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Modern Forms number based on a config entry."""
    coordinator = config_entry.runtime_data

    if not coordinator.data.has_wind():
        return

    async_add_entities(
        [ModernFormsBreezeIntensityNumber(config_entry.entry_id, coordinator)]
    )


class ModernFormsBreezeIntensityNumber(ModernFormsDeviceEntity, NumberEntity):
    """Defines a Modern Forms breeze intensity number."""

    _attr_translation_key = "breeze_intensity"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 3
    _attr_native_step = 1

    def __init__(
        self, entry_id: str, coordinator: ModernFormsDataUpdateCoordinator
    ) -> None:
        """Initialize Modern Forms breeze intensity number."""
        super().__init__(entry_id=entry_id, coordinator=coordinator)
        self._attr_unique_id = (
            f"{self.coordinator.data.info.mac_address}_breeze_intensity"
        )

    @property
    @override
    def native_value(self) -> int:
        """Return the current breeze intensity."""
        return self.coordinator.data.state.wind_speed

    @modernforms_exception_handler
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the breeze intensity."""
        await self.coordinator.modern_forms.fan(wind_speed=int(value))
