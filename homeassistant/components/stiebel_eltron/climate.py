"""Support for stiebel_eltron climate platform."""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.exceptions import ModbusException
from pystiebeleltron.lwz import OperatingMode

from homeassistant.components.climate import (
    PRESET_COMFORT,
    PRESET_ECO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import StiebelEltronConfigEntry
from .coordinator import StiebelEltronDataCoordinator

DEPENDENCIES = ["stiebel_eltron"]

_LOGGER = logging.getLogger(__name__)

CLIMATE_HK_1 = "climate_hk_1"

# Mapping STIEBEL ELTRON states to homeassistant states/preset.
LWZ_TO_HA_HVAC = {
    OperatingMode.AUTOMATIC: HVACMode.AUTO,
    OperatingMode.MANUAL_MODE: HVACMode.HEAT,
    OperatingMode.STANDBY: HVACMode.AUTO,
    OperatingMode.DAY_MODE: HVACMode.AUTO,
    OperatingMode.SETBACK_MODE: HVACMode.AUTO,
    OperatingMode.DHW: HVACMode.OFF,
    OperatingMode.EMERGENCY_OPERATION: HVACMode.AUTO,
}

HA_TO_LWZ_HVAC = {
    HVACMode.AUTO: OperatingMode.AUTOMATIC,
    HVACMode.OFF: OperatingMode.DHW,
    HVACMode.HEAT: OperatingMode.MANUAL_MODE,
}

# Custom presets
PRESET_PROGRAM = "program"
PRESET_WATER_HEATING = "water_heating"
PRESET_EMERGENCY = "emergency"
PRESET_READY = "ready"
PRESET_MANUAL = "manual"
PRESET_AUTO = "auto"

LWZ_TO_HA_PRESET = {
    OperatingMode.STANDBY: PRESET_READY,
    OperatingMode.DAY_MODE: PRESET_COMFORT,
    OperatingMode.SETBACK_MODE: PRESET_ECO,
    OperatingMode.DHW: PRESET_WATER_HEATING,
    OperatingMode.AUTOMATIC: PRESET_AUTO,
    OperatingMode.MANUAL_MODE: PRESET_MANUAL,
    OperatingMode.EMERGENCY_OPERATION: PRESET_EMERGENCY,
}

HA_TO_LWZ_PRESET = {
    PRESET_READY: OperatingMode.STANDBY,
    PRESET_COMFORT: OperatingMode.DAY_MODE,
    PRESET_ECO: OperatingMode.SETBACK_MODE,
    PRESET_WATER_HEATING: OperatingMode.DHW,
    PRESET_AUTO: OperatingMode.AUTOMATIC,
    PRESET_MANUAL: OperatingMode.MANUAL_MODE,
    PRESET_EMERGENCY: OperatingMode.EMERGENCY_OPERATION,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StiebelEltronConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up STIEBEL ELTRON climate platform."""

    async_add_entities([StiebelEltron(entry.entry_id, entry.runtime_data)])


class StiebelEltron(CoordinatorEntity[StiebelEltronDataCoordinator], ClimateEntity):
    """Representation of a STIEBEL ELTRON heat pump."""

    _attr_hvac_modes = list(HA_TO_LWZ_HVAC)
    _attr_preset_modes = list(HA_TO_LWZ_PRESET)
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = PRECISION_TENTHS
    _attr_min_temp = 10.0
    _attr_max_temp = 30.0

    def __init__(
        self, unique_id: str, coordinator: StiebelEltronDataCoordinator
    ) -> None:
        """Initialize the unit."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{unique_id}-climate_hk_1"
        # Initialize runtime attributes to avoid attribute errors
        self._set_attr()

    @property
    def extra_state_attributes(self) -> dict[str, bool | None]:
        """Return device specific state attributes."""
        filter_alarm = self.coordinator.api_client.get_filter_alarm_status()
        return {"filter_alarm": filter_alarm}

    def _handle_coordinator_update(self) -> None:
        """Handle entity update."""
        self._set_attr()
        super()._handle_coordinator_update()

    def _set_attr(self) -> None:
        lwz_api_client = self.coordinator.api_client

        self._attr_target_temperature = lwz_api_client.get_target_temp()
        self._attr_current_temperature = lwz_api_client.get_current_temp()
        self._attr_current_humidity = lwz_api_client.get_current_humidity()
        operation = lwz_api_client.get_operation()
        self._attr_hvac_mode = LWZ_TO_HA_HVAC.get(operation)
        self._attr_preset_mode = LWZ_TO_HA_PRESET.get(operation)

    async def async_added_to_hass(self) -> None:
        """Handle when entity is added to hass."""
        self._handle_coordinator_update()
        return await super().async_added_to_hass()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        if self.preset_mode:
            return
        new_mode = HA_TO_LWZ_HVAC.get(hvac_mode)
        if new_mode is not None:
            _LOGGER.debug(
                "async_set_hvac_mode: %s -> %s", self._attr_hvac_mode, new_mode
            )
            try:
                await self.coordinator.api_client.set_operation(new_mode)
            except ModbusException as e:
                _LOGGER.error("Error setting HVAC mode: %s", e)
                raise HomeAssistantError("Failed to set HVAC mode") from e
            else:
                await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is not None:
            _LOGGER.debug("async_set_temperature: %s", target_temperature)
            try:
                await self.coordinator.api_client.set_target_temp(target_temperature)
            except ModbusException as e:
                _LOGGER.error("Error setting target temperature: %s", e)
                raise HomeAssistantError("Failed to set target temperature") from e
            else:
                await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        new_preset = HA_TO_LWZ_PRESET.get(preset_mode)
        if new_preset is not None:
            _LOGGER.debug(
                "async_set_preset_mode: %s -> %s", self._attr_preset_mode, new_preset
            )
            try:
                await self.coordinator.api_client.set_operation(new_preset)
            except ModbusException as e:
                _LOGGER.error("Error setting preset mode: %s", e)
                raise HomeAssistantError("Failed to set preset mode") from e
            else:
                await self.coordinator.async_request_refresh()
