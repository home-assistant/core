"""Support for the Airzone water heater."""
from __future__ import annotations

from typing import Any, Final

from aioairzone.common import HotWaterOperation
from aioairzone.const import (
    API_ACS_ON,
    API_ACS_POWER_MODE,
    API_ACS_SET_POINT,
    AZD_HOT_WATER,
    AZD_NAME,
    AZD_OPERATION,
    AZD_OPERATIONS,
    AZD_TEMP,
    AZD_TEMP_MAX,
    AZD_TEMP_MIN,
    AZD_TEMP_SET,
    AZD_TEMP_UNIT,
)

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TEMP_UNIT_LIB_TO_HASS
from .coordinator import AirzoneUpdateCoordinator
from .entity import AirzoneHotWaterEntity

OPERATION_LIB_TO_HASS: Final[dict[HotWaterOperation, str]] = {
    HotWaterOperation.Off: STATE_OFF,
    HotWaterOperation.On: STATE_ECO,
    HotWaterOperation.Powerful: STATE_PERFORMANCE,
}

OPERATION_MODE_TO_DHW_PARAMS: Final[dict[str, dict[str, Any]]] = {
    STATE_OFF: {
        API_ACS_ON: 0,
    },
    STATE_ECO: {
        API_ACS_ON: 1,
        API_ACS_POWER_MODE: 0,
    },
    STATE_PERFORMANCE: {
        API_ACS_ON: 1,
        API_ACS_POWER_MODE: 1,
    },
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Airzone sensors from a config_entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if AZD_HOT_WATER in coordinator.data:
        async_add_entities([AirzoneWaterHeater(coordinator, entry)])


class AirzoneWaterHeater(AirzoneHotWaterEntity, WaterHeaterEntity):
    """Define an Airzone Water Heater."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize Airzone water heater entity."""
        super().__init__(coordinator, entry)

        self._attr_name = self.get_airzone_value(AZD_NAME)
        self._attr_unique_id = f"{self._attr_unique_id}_dhw"
        self._attr_supported_features = (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.ON_OFF
            | WaterHeaterEntityFeature.OPERATION_MODE
        )
        self._attr_operation_list = [
            OPERATION_LIB_TO_HASS[operation]
            for operation in self.get_airzone_value(AZD_OPERATIONS)
        ]
        self._attr_temperature_unit = TEMP_UNIT_LIB_TO_HASS[
            self.get_airzone_value(AZD_TEMP_UNIT)
        ]

        self._async_update_attrs()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        params: dict[str, Any] = {
            API_ACS_ON: 0,
        }
        await self._async_update_dhw_params(params)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        params: dict[str, Any] = {
            API_ACS_ON: 1,
        }
        await self._async_update_dhw_params(params)

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        params: dict[str, Any] = OPERATION_MODE_TO_DHW_PARAMS.get(operation_mode, {})
        await self._async_update_dhw_params(params)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        params: dict[str, Any] = {}
        if ATTR_TEMPERATURE in kwargs:
            params[API_ACS_SET_POINT] = kwargs[ATTR_TEMPERATURE]
        await self._async_update_dhw_params(params)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update water heater attributes."""
        self._attr_current_temperature = self.get_airzone_value(AZD_TEMP)
        self._attr_current_operation = OPERATION_LIB_TO_HASS[
            self.get_airzone_value(AZD_OPERATION)
        ]
        self._attr_max_temp = self.get_airzone_value(AZD_TEMP_MAX)
        self._attr_min_temp = self.get_airzone_value(AZD_TEMP_MIN)
        self._attr_target_temperature = self.get_airzone_value(AZD_TEMP_SET)
