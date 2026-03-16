"""Support for WaterFurnace climate entity."""

from __future__ import annotations

from typing import Any

from waterfurnace.waterfurnace import WFException

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WaterFurnaceConfigEntry
from .coordinator import WaterFurnaceCoordinator
from .entity import WaterFurnaceEntity

PARALLEL_UPDATES = 0

# Maps ActiveSettings.mode string to HVACMode
ACTIVE_MODE_TO_HVAC: dict[str, HVACMode] = {
    "Off": HVACMode.OFF,
    "Auto": HVACMode.AUTO,
    "Cool": HVACMode.COOL,
    "Heat": HVACMode.HEAT,
    "E-Heat": HVACMode.HEAT,
}

# Maps HVACMode to library's integer mode
HVAC_TO_WF_MODE: dict[HVACMode, int] = {
    HVACMode.OFF: 0,
    HVACMode.AUTO: 1,
    HVACMode.COOL: 2,
    HVACMode.HEAT: 3,
}

# Maps WFReading.mode string to HVACAction
FURNACE_MODE_TO_ACTION: dict[str, HVACAction] = {
    "Standby": HVACAction.IDLE,
    "Fan Only": HVACAction.FAN,
    "Cooling 1": HVACAction.COOLING,
    "Cooling 2": HVACAction.COOLING,
    "Reheat": HVACAction.HEATING,
    "Heating 1": HVACAction.HEATING,
    "Heating 2": HVACAction.HEATING,
    "E-Heat": HVACAction.HEATING,
    "Aux Heat": HVACAction.HEATING,
    "Lockout": HVACAction.OFF,
}

# Library temperature limits (Fahrenheit)
HEATING_MIN = 40
HEATING_MAX = 80
COOLING_MIN = 60
COOLING_MAX = 90


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WaterFurnaceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WaterFurnace climate from a config entry."""
    async_add_entities(
        WaterFurnaceClimate(device_data.realtime)
        for device_data in config_entry.runtime_data.values()
    )


class WaterFurnaceClimate(WaterFurnaceEntity, ClimateEntity):
    """Climate entity for WaterFurnace geothermal systems."""

    _attr_name = None
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.TARGET_HUMIDITY
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_temp = HEATING_MIN
    _attr_max_temp = COOLING_MAX
    _attr_min_humidity = 15
    _attr_max_humidity = 95

    def __init__(self, coordinator: WaterFurnaceCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unit}_climate"

    @property
    def current_temperature(self) -> float | None:
        """Return the current room temperature."""
        return self.coordinator.data.tstatroomtemp

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self.coordinator.data.tstatrelativehumidity

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        return ACTIVE_MODE_TO_HVAC.get(self.coordinator.data.activesettings.mode)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        return FURNACE_MODE_TO_ACTION.get(self.coordinator.data.mode)

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature (single setpoint modes)."""
        if self.hvac_mode == HVACMode.COOL:
            return self.coordinator.data.tstatcoolingsetpoint
        if self.hvac_mode == HVACMode.HEAT:
            return self.coordinator.data.tstatheatingsetpoint
        return None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the upper bound target temperature (Auto mode)."""
        if self.hvac_mode == HVACMode.AUTO:
            return self.coordinator.data.tstatcoolingsetpoint
        return None

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lower bound target temperature (Auto mode)."""
        if self.hvac_mode == HVACMode.AUTO:
            return self.coordinator.data.tstatheatingsetpoint
        return None

    @property
    def target_humidity(self) -> float | None:
        """Return the target humidity."""
        return self.coordinator.data.tstathumidsetpoint

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.client.set_mode, HVAC_TO_WF_MODE[hvac_mode]
            )
        except WFException as err:
            raise HomeAssistantError(f"Failed to set HVAC mode: {err}") from err
        # Optimistically update local state so the UI reflects the change
        # immediately. The device takes a few seconds to apply writes, so
        # a forced refresh would read stale data and briefly revert the UI.
        # The next regular poll (10s) will confirm the real device state.
        self.coordinator.data.activesettings.activemode = HVAC_TO_WF_MODE[hvac_mode]
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature(s)."""
        try:
            if (low := kwargs.get(ATTR_TARGET_TEMP_LOW)) is not None and (
                high := kwargs.get(ATTR_TARGET_TEMP_HIGH)
            ) is not None:
                await self.hass.async_add_executor_job(
                    self.coordinator.client.set_heating_setpoint, low
                )
                await self.hass.async_add_executor_job(
                    self.coordinator.client.set_cooling_setpoint, high
                )
                self.coordinator.data.tstatheatingsetpoint = low
                self.coordinator.data.tstatcoolingsetpoint = high
            elif (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
                if self.hvac_mode == HVACMode.COOL:
                    await self.hass.async_add_executor_job(
                        self.coordinator.client.set_cooling_setpoint, temp
                    )
                    self.coordinator.data.tstatcoolingsetpoint = temp
                else:
                    await self.hass.async_add_executor_job(
                        self.coordinator.client.set_heating_setpoint, temp
                    )
                    self.coordinator.data.tstatheatingsetpoint = temp
        except WFException as err:
            raise HomeAssistantError(f"Failed to set temperature: {err}") from err
        self.async_write_ha_state()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the target humidity."""
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.client.set_humidity, humidity
            )
        except WFException as err:
            raise HomeAssistantError(f"Failed to set humidity: {err}") from err
        self.coordinator.data.tstathumidsetpoint = humidity
        self.async_write_ha_state()
