"""Support for the Airzone Cloud water heater."""

from __future__ import annotations

from typing import Any, Final

from aioairzone_cloud.common import HotWaterOperation, TemperatureUnit
from aioairzone_cloud.const import (
    API_OPTS,
    API_POWER,
    API_POWERFUL_MODE,
    API_SETPOINT,
    API_UNITS,
    API_VALUE,
    AZD_HOT_WATERS,
    AZD_OPERATION,
    AZD_OPERATIONS,
    AZD_TEMP,
    AZD_TEMP_SET,
    AZD_TEMP_SET_MAX,
    AZD_TEMP_SET_MIN,
)

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirzoneCloudConfigEntry
from .coordinator import AirzoneUpdateCoordinator
from .entity import AirzoneHotWaterEntity

OPERATION_LIB_TO_HASS: Final[dict[HotWaterOperation, str]] = {
    HotWaterOperation.Off: STATE_OFF,
    HotWaterOperation.On: STATE_ECO,
    HotWaterOperation.Powerful: STATE_PERFORMANCE,
}

OPERATION_MODE_TO_DHW_PARAMS: Final[dict[str, dict[str, Any]]] = {
    STATE_OFF: {
        API_POWER: {
            API_VALUE: False,
        },
    },
    STATE_ECO: {
        API_POWER: {
            API_VALUE: True,
        },
        API_POWERFUL_MODE: {
            API_VALUE: False,
        },
    },
    STATE_PERFORMANCE: {
        API_POWER: {
            API_VALUE: True,
        },
        API_POWERFUL_MODE: {
            API_VALUE: True,
        },
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirzoneCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Airzone Cloud Water Heater from a config_entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        AirzoneWaterHeater(
            coordinator,
            dhw_id,
            dhw_data,
        )
        for dhw_id, dhw_data in coordinator.data.get(AZD_HOT_WATERS, {}).items()
    )


class AirzoneWaterHeater(AirzoneHotWaterEntity, WaterHeaterEntity):
    """Define an Airzone Cloud Water Heater."""

    _attr_name = None
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        dhw_id: str,
        dhw_data: dict,
    ) -> None:
        """Initialize Airzone Cloud Water Heater."""
        super().__init__(coordinator, dhw_id, dhw_data)

        self._attr_unique_id = dhw_id
        self._attr_operation_list = [
            OPERATION_LIB_TO_HASS[operation]
            for operation in self.get_airzone_value(AZD_OPERATIONS)
        ]

        self._async_update_attrs()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        params = {
            API_POWER: {
                API_VALUE: False,
            },
        }
        await self._async_update_params(params)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        params = {
            API_POWER: {
                API_VALUE: True,
            },
        }
        await self._async_update_params(params)

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        params = OPERATION_MODE_TO_DHW_PARAMS.get(operation_mode, {})
        await self._async_update_params(params)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        params: dict[str, Any] = {}
        if ATTR_TEMPERATURE in kwargs:
            params[API_SETPOINT] = {
                API_VALUE: kwargs[ATTR_TEMPERATURE],
                API_OPTS: {
                    API_UNITS: TemperatureUnit.CELSIUS.value,
                },
            }
        await self._async_update_params(params)

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
        self._attr_max_temp = self.get_airzone_value(AZD_TEMP_SET_MAX)
        self._attr_min_temp = self.get_airzone_value(AZD_TEMP_SET_MIN)
        self._attr_target_temperature = self.get_airzone_value(AZD_TEMP_SET)
