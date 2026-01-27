"""BSBLAN platform to control a compatible Water Heater Device."""

from __future__ import annotations

from typing import Any

from bsblan import BSBLANError, SetHotWaterParam

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_OFF,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BSBLanConfigEntry, BSBLanData
from .const import DOMAIN
from .entity import BSBLanDualCoordinatorEntity

PARALLEL_UPDATES = 1

# Mapping between BSBLan and HA operation modes
OPERATION_MODES = {
    "Eco": STATE_ECO,  # Energy saving mode
    "Off": STATE_OFF,  # Protection mode
    "On": STATE_ON,  # Continuous comfort mode
}

OPERATION_MODES_REVERSE = {v: k for k, v in OPERATION_MODES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BSBLanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BSBLAN water heater based on a config entry."""
    data = entry.runtime_data

    # Only create water heater entity if DHW (Domestic Hot Water) is available
    # Check if we have any DHW-related data indicating water heater support
    dhw_data = data.fast_coordinator.data.dhw
    if (
        dhw_data.operating_mode is None
        and dhw_data.nominal_setpoint is None
        and dhw_data.dhw_actual_value_top_temperature is None
    ):
        # No DHW functionality available, skip water heater setup
        return

    async_add_entities([BSBLANWaterHeater(data)])


class BSBLANWaterHeater(BSBLanDualCoordinatorEntity, WaterHeaterEntity):
    """Defines a BSBLAN water heater entity."""

    _attr_name = None
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )

    def __init__(self, data: BSBLanData) -> None:
        """Initialize BSBLAN water heater."""
        super().__init__(data.fast_coordinator, data.slow_coordinator, data)
        self._attr_unique_id = format_mac(data.device.MAC)
        self._attr_operation_list = list(OPERATION_MODES_REVERSE.keys())

        # Set temperature unit
        self._attr_temperature_unit = data.fast_coordinator.client.get_temperature_unit
        # Initialize available attribute to resolve multiple inheritance conflict
        self._attr_available = True

        # Set temperature limits based on device capabilities from slow coordinator
        # For min_temp: Use reduced_setpoint from config data (slow polling)
        if (
            data.slow_coordinator.data
            and data.slow_coordinator.data.dhw_config is not None
            and data.slow_coordinator.data.dhw_config.reduced_setpoint is not None
            and hasattr(data.slow_coordinator.data.dhw_config.reduced_setpoint, "value")
        ):
            self._attr_min_temp = float(
                data.slow_coordinator.data.dhw_config.reduced_setpoint.value
            )
        else:
            self._attr_min_temp = 10.0  # Default minimum

        # For max_temp: Use nominal_setpoint_max from config data (slow polling)
        if (
            data.slow_coordinator.data
            and data.slow_coordinator.data.dhw_config is not None
            and data.slow_coordinator.data.dhw_config.nominal_setpoint_max is not None
            and hasattr(
                data.slow_coordinator.data.dhw_config.nominal_setpoint_max, "value"
            )
        ):
            self._attr_max_temp = float(
                data.slow_coordinator.data.dhw_config.nominal_setpoint_max.value
            )
        else:
            self._attr_max_temp = 65.0  # Default maximum

    @property
    def current_operation(self) -> str | None:
        """Return current operation."""
        if self.coordinator.data.dhw.operating_mode is None:
            return None
        current_mode = self.coordinator.data.dhw.operating_mode.desc
        return OPERATION_MODES.get(current_mode)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.coordinator.data.dhw.dhw_actual_value_top_temperature is None:
            return None
        return self.coordinator.data.dhw.dhw_actual_value_top_temperature.value

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.coordinator.data.dhw.nominal_setpoint is None:
            return None
        return self.coordinator.data.dhw.nominal_setpoint.value

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        try:
            await self.coordinator.client.set_hot_water(
                SetHotWaterParam(nominal_setpoint=temperature)
            )
        except BSBLANError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_temperature_error",
            ) from err

        await self.coordinator.async_request_refresh()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        bsblan_mode = OPERATION_MODES_REVERSE.get(operation_mode)
        try:
            await self.coordinator.client.set_hot_water(
                SetHotWaterParam(operating_mode=bsblan_mode)
            )
        except BSBLANError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_operation_mode_error",
            ) from err

        await self.coordinator.async_request_refresh()
