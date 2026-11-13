"""Support for Hot Spring number entities."""

from typing import override

from hotspring import TemperatureUnit

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

MIN_TEMP_FAHRENHEIT = 80.0
MAX_TEMP_FAHRENHEIT = 104.0
STEP_FAHRENHEIT = 1.0

MIN_TEMP_CELSIUS = 26.0
MAX_TEMP_CELSIUS = 40.0
STEP_CELSIUS = 0.5

TARGET_TEMPERATURE_DESCRIPTION = NumberEntityDescription(
    key="target_temperature",
    translation_key="target_temperature",
    device_class=NumberDeviceClass.TEMPERATURE,
)

SALT_OUTPUT_LEVEL_DESCRIPTION = NumberEntityDescription(
    key="salt_output_level",
    translation_key="salt_output_level",
    native_min_value=0.0,
    native_max_value=10.0,
    native_step=1.0,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HotSpringConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hot Spring number entities."""
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = [
        HotSpringNumberEntity(coordinator, TARGET_TEMPERATURE_DESCRIPTION)
    ]
    if coordinator.data.water_care.cartridge_installed:
        entities.append(
            HotSpringSaltOutputLevelEntity(coordinator, SALT_OUTPUT_LEVEL_DESCRIPTION)
        )
    async_add_entities(entities)


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
    def _is_celsius(self) -> bool:
        """Return True if the spa is configured in Celsius."""
        return self.coordinator.data.heater.temperature_unit is TemperatureUnit.CELSIUS

    @property
    @override
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        if self._is_celsius:
            return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT

    @property
    @override
    def native_min_value(self) -> float:
        """Return the minimum value."""
        if self._is_celsius:
            return MIN_TEMP_CELSIUS
        return MIN_TEMP_FAHRENHEIT

    @property
    @override
    def native_max_value(self) -> float:
        """Return the maximum value."""
        if self._is_celsius:
            return MAX_TEMP_CELSIUS
        return MAX_TEMP_FAHRENHEIT

    @property
    @override
    def native_step(self) -> float:
        """Return the step value."""
        if self._is_celsius:
            return STEP_CELSIUS
        return STEP_FAHRENHEIT

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current target temperature."""
        return self.coordinator.data.heater.set_temperature

    @hotspring_exception_handler
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the target temperature."""
        target = round(value / self.native_step) * self.native_step
        await self.coordinator.hotspring.set_temperature(target)
        self.coordinator.async_set_updated_data(self.coordinator.data)


class HotSpringSaltOutputLevelEntity(HotSpringEntity, NumberEntity):
    """Defines a Hot Spring salt output level number entity."""

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
        """Return the current salt output level."""
        return self.coordinator.data.water_care.level

    @hotspring_exception_handler
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the salt output level."""
        await self.coordinator.hotspring.set_water_care_level(int(value))
        self.coordinator.async_set_updated_data(self.coordinator.data)
