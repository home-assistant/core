"""Support for WaterFurnace climate entity."""

from __future__ import annotations

from typing import Any

from waterfurnace.waterfurnace import WFException

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
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
    "Auto": HVACMode.HEAT_COOL,
    "Cool": HVACMode.COOL,
    "Heat": HVACMode.HEAT,
    "E-Heat": HVACMode.HEAT,
}

# Maps HVACMode to library's integer mode
HVAC_TO_WF_MODE: dict[HVACMode, int] = {
    HVACMode.OFF: 0,
    HVACMode.HEAT_COOL: 1,
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
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.HEAT_COOL]
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_humidity = 15
    _attr_max_humidity = 95

    def __init__(self, coordinator: WaterFurnaceCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.unit

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature based on current mode."""
        if self.hvac_mode == HVACMode.COOL:
            return COOLING_MIN
        return HEATING_MIN

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature based on current mode."""
        if self.hvac_mode == HVACMode.HEAT:
            return HEATING_MAX
        return COOLING_MAX

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
        """Return the upper bound target temperature (Heat/Cool mode)."""
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return self.coordinator.data.tstatcoolingsetpoint
        return None

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lower bound target temperature (Heat/Cool mode)."""
        if self.hvac_mode == HVACMode.HEAT_COOL:
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
        except (WFException, ValueError) as err:
            raise HomeAssistantError(f"Failed to set HVAC mode: {err}") from err

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature(s)."""
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_set_hvac_mode(hvac_mode)

        low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temp = kwargs.get(ATTR_TEMPERATURE)
        current_mode = hvac_mode if hvac_mode is not None else self.hvac_mode
        try:
            await self.hass.async_add_executor_job(
                self._set_temperature, low, high, temp, current_mode
            )
        except (WFException, ValueError) as err:
            raise HomeAssistantError(f"Failed to set temperature: {err}") from err

    def _set_temperature(
        self,
        low: float | None,
        high: float | None,
        temp: float | None,
        current_mode: HVACMode | None,
    ) -> None:
        """Send temperature setpoint(s) to the device."""
        client = self.coordinator.client
        if low is not None and high is not None:
            client.set_heating_setpoint(low)
            client.set_cooling_setpoint(high)
        elif temp is not None:
            if current_mode == HVACMode.COOL:
                client.set_cooling_setpoint(temp)
            else:
                client.set_heating_setpoint(temp)

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the target humidity."""
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.client.set_humidity, humidity
            )
        except (WFException, ValueError) as err:
            raise HomeAssistantError(f"Failed to set humidity: {err}") from err
