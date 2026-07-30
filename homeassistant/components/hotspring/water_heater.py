"""Support for Hot Spring water heater."""

from typing import Any, override

from hotspring import HotSpringConnectionError, HotSpringError

from homeassistant.components.water_heater import (
    STATE_OFF,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_ON, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HotSpringConfigEntry, HotSpringDataUpdateCoordinator
from .entity import HotSpringEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HotSpringConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hot Spring water heater entity."""
    async_add_entities([HotSpringWaterHeaterEntity(entry.runtime_data)])


class HotSpringWaterHeaterEntity(HotSpringEntity, WaterHeaterEntity):
    """Defines a Hot Spring water heater entity."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_temp = 80.0
    _attr_max_temp = 104.0
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE

    def __init__(self, coordinator: HotSpringDataUpdateCoordinator) -> None:
        """Initialize the water heater entity."""
        super().__init__(coordinator, "water_heater")

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.data.heater.current_temperature

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.coordinator.data.heater.set_temperature

    @property
    @override
    def current_operation(self) -> str | None:
        """Return the current operation mode."""
        if self.coordinator.data.heater.is_on:
            return STATE_ON
        return STATE_OFF

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            try:
                await self.coordinator.hotspring.set_temperature(temperature)
            except HotSpringConnectionError as error:
                self.coordinator.last_update_success = False
                self.coordinator.async_update_listeners()
                raise HomeAssistantError("Error communicating with Hot Spring API") from error
            except HotSpringError as error:
                raise HomeAssistantError("Invalid response from Hot Spring API") from error
            await self.coordinator.async_request_refresh()

