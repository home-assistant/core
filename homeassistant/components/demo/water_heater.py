"""Demo platform that offers a fake water heater device."""

from __future__ import annotations

from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

SUPPORT_FLAGS_HEATER = (
    WaterHeaterEntityFeature.TARGET_TEMPERATURE
    | WaterHeaterEntityFeature.ON_OFF
    | WaterHeaterEntityFeature.OPERATION_MODE
    | WaterHeaterEntityFeature.AWAY_MODE
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    async_add_entities(
        [
            DemoWaterHeater(
                "Demo Water Heater", 119, UnitOfTemperature.FAHRENHEIT, False, "eco", 1
            ),
            DemoWaterHeater(
                "Demo Water Heater Celsius",
                45,
                UnitOfTemperature.CELSIUS,
                True,
                "eco",
                1,
            ),
        ]
    )


class DemoWaterHeater(WaterHeaterEntity):
    """Representation of a demo water_heater device."""

    _attr_should_poll = False
    _attr_supported_features = SUPPORT_FLAGS_HEATER

    def __init__(
        self,
        name: str,
        target_temperature: int,
        unit_of_measurement: str,
        away: bool,
        current_operation: str,
        target_temperature_step: float,
    ) -> None:
        """Initialize the water_heater device."""
        self._attr_name = name
        if target_temperature is not None:
            self._attr_supported_features |= WaterHeaterEntityFeature.TARGET_TEMPERATURE
        if away is not None:
            self._attr_supported_features |= WaterHeaterEntityFeature.AWAY_MODE
        if current_operation is not None:
            self._attr_supported_features |= WaterHeaterEntityFeature.OPERATION_MODE
        self._attr_target_temperature = target_temperature
        self._attr_temperature_unit = unit_of_measurement
        self._attr_is_away_mode_on = away
        self._attr_current_operation = current_operation
        self._attr_operation_list = [
            "eco",
            "electric",
            "performance",
            "high_demand",
            "heat_pump",
            "gas",
            "off",
        ]
        self._attr_target_temperature_step = target_temperature_step

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        self._attr_target_temperature = kwargs.get(ATTR_TEMPERATURE)
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        self._attr_current_operation = operation_mode
        self.schedule_update_ha_state()

    def turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        self._attr_is_away_mode_on = True
        self.schedule_update_ha_state()

    def turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        self._attr_is_away_mode_on = False
        self.schedule_update_ha_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on water heater."""
        self.set_operation_mode("eco")

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off water heater."""
        self.set_operation_mode("off")
