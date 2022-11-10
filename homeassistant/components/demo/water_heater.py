"""Demo platform that offers a fake water heater device."""
from __future__ import annotations

from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterCurrentOperation,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    WaterHeaterOperationMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Demo water_heater devices."""
    async_add_entities(
        [
            DemoWaterHeater(
                "water_heater_1",
                "Demo Water Heater",
                119,
                TEMP_FAHRENHEIT,
                [
                    WaterHeaterOperationMode.ON,
                    WaterHeaterOperationMode.AWAY,
                    WaterHeaterOperationMode.BOOST,
                ],
                WaterHeaterOperationMode.ON,
                WaterHeaterCurrentOperation.HEATING,
                "eco",
                ["eco", "normal"],
            ),
            DemoWaterHeater(
                "water_heater_2",
                "Demo Water Heater Celsius",
                45,
                TEMP_CELSIUS,
                [WaterHeaterOperationMode.ON, WaterHeaterOperationMode.AWAY],
                WaterHeaterOperationMode.AWAY,
                WaterHeaterCurrentOperation.IDLE,
                None,
                None,
            ),
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoWaterHeater(WaterHeaterEntity):
    """Representation of a demo water_heater device."""

    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        name: str,
        target_temperature: int,
        unit_of_measurement: str,
        operation_modes: list[WaterHeaterOperationMode],
        operation_mode: WaterHeaterOperationMode,
        current_operation: WaterHeaterCurrentOperation,
        preset_mode: str | None,
        preset_modes: list[str] | None,
    ) -> None:
        """Initialize the water_heater device."""
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=self.name,
        )
        self._attr_supported_features = 0
        if target_temperature is not None:
            self._attr_supported_features = (
                self._attr_supported_features
                | WaterHeaterEntityFeature.TARGET_TEMPERATURE
            )
        if operation_modes:
            self._attr_supported_features = (
                self._attr_supported_features | WaterHeaterEntityFeature.OPERATION_MODE
            )

        if preset_modes:
            self._attr_supported_features = (
                self._attr_supported_features | WaterHeaterEntityFeature.PRESET_MODE
            )

        self._attr_target_temperature = target_temperature
        self._attr_temperature_unit = unit_of_measurement
        self._attr_current_operation = current_operation
        self._attr_operation_modes = operation_modes
        self._attr_operation_mode = operation_mode
        self._attr_preset_mode = preset_mode
        self._attr_preset_modes = preset_modes

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        self._attr_target_temperature = kwargs.get(ATTR_TEMPERATURE)
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode: WaterHeaterOperationMode) -> None:
        """Set new operation mode."""
        self._attr_operation_mode = operation_mode
        self.schedule_update_ha_state()

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        self._attr_preset_mode = preset_mode
        self.schedule_update_ha_state()
