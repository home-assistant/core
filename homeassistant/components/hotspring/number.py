"""Support for Hot Spring number entities."""

from typing import override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HotSpringConfigEntry, HotSpringDataUpdateCoordinator
from .entity import HotSpringEntity
from .helpers import hotspring_exception_handler

PARALLEL_UPDATES = 1

TARGET_TEMPERATURE_DESCRIPTION = NumberEntityDescription(
    key="target_temperature",
    translation_key="target_temperature",
    device_class=NumberDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
    native_min_value=80.0,
    native_max_value=104.0,
    native_step=1.0,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HotSpringConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hot Spring number entities."""
    async_add_entities(
        [HotSpringNumberEntity(entry.runtime_data, TARGET_TEMPERATURE_DESCRIPTION)]
    )


class HotSpringNumberEntity(HotSpringEntity, NumberEntity):
    """Defines a Hot Spring number entity."""

    entity_description: NumberEntityDescription

    def __init__(
        self,
        coordinator: HotSpringDataUpdateCoordinator,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current target temperature."""
        return self.coordinator.data.heater.set_temperature

    @hotspring_exception_handler
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the target temperature."""
        await self.coordinator.hotspring.set_temperature(round(value))
        self.coordinator.async_set_updated_data(self.coordinator.data)
