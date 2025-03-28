"""BSBLAN platform to control a compatible Water Heater Device."""

from __future__ import annotations

from typing import Any

from bsblan import BSBLANError

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
from .entity import BSBLanEntity

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
    async_add_entities([BSBLANWaterHeater(data)])


class BSBLANWaterHeater(BSBLanEntity, WaterHeaterEntity):
    """Defines a BSBLAN water heater entity."""

    _attr_name = None
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )

    def __init__(self, data: BSBLanData) -> None:
        """Initialize BSBLAN water heater."""
        super().__init__(data.coordinator, data)
        self._attr_unique_id = format_mac(data.device.MAC)
        self._attr_operation_list = list(OPERATION_MODES_REVERSE.keys())

        # Set temperature limits based on device capabilities
        self._attr_temperature_unit = data.coordinator.client.get_temperature_unit
        self._attr_min_temp = data.coordinator.data.dhw.reduced_setpoint.value
        self._attr_max_temp = data.coordinator.data.dhw.nominal_setpoint_max.value

    @property
    def current_operation(self) -> str | None:
        """Return current operation."""
        current_mode = self.coordinator.data.dhw.operating_mode.desc
        return OPERATION_MODES.get(current_mode)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.data.dhw.dhw_actual_value_top_temperature.value

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.coordinator.data.dhw.nominal_setpoint.value

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        try:
            await self.coordinator.client.set_hot_water(nominal_setpoint=temperature)
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
            await self.coordinator.client.set_hot_water(operating_mode=bsblan_mode)
        except BSBLANError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_operation_mode_error",
            ) from err

        await self.coordinator.async_request_refresh()
