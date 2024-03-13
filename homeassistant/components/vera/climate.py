"""Support for Vera thermostats."""
from __future__ import annotations

from typing import Any

import pyvera as veraApi

from homeassistant.components.climate import (
    ENTITY_ID_FORMAT,
    FAN_AUTO,
    FAN_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VeraDevice
from .common import ControllerData, get_controller_data

FAN_OPERATION_LIST = [FAN_ON, FAN_AUTO]

SUPPORT_HVAC = [HVACMode.COOL, HVACMode.HEAT, HVACMode.HEAT_COOL, HVACMode.OFF]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    controller_data = get_controller_data(hass, entry)
    async_add_entities(
        [
            VeraThermostat(device, controller_data)
            for device in controller_data.devices[Platform.CLIMATE]
        ],
        True,
    )


class VeraThermostat(VeraDevice[veraApi.VeraThermostat], ClimateEntity):
    """Representation of a Vera Thermostat."""

    _attr_hvac_modes = SUPPORT_HVAC
    _attr_fan_modes = FAN_OPERATION_LIST
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self, vera_device: veraApi.VeraThermostat, controller_data: ControllerData
    ) -> None:
        """Initialize the Vera device."""
        VeraDevice.__init__(self, vera_device, controller_data)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        mode = self.vera_device.get_hvac_mode()
        if mode == "HeatOn":
            return HVACMode.HEAT
        if mode == "CoolOn":
            return HVACMode.COOL
        if mode == "AutoChangeOver":
            return HVACMode.HEAT_COOL
        return HVACMode.OFF

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        if self.vera_device.get_fan_mode() == "ContinuousOn":
            return FAN_ON
        return FAN_AUTO

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target temperature."""
        if fan_mode == FAN_ON:
            self.vera_device.fan_on()
        else:
            self.vera_device.fan_auto()

        self.schedule_update_ha_state()

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        vera_temp_units = self.vera_device.vera_controller.temperature_units

        if vera_temp_units == "F":
            return UnitOfTemperature.FAHRENHEIT

        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.vera_device.get_current_temperature()

    @property
    def operation(self) -> str:
        """Return current operation ie. heat, cool, idle."""
        return self.vera_device.get_hvac_mode()

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.vera_device.get_current_goal_temperature()

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self.vera_device.set_temperature(kwargs.get(ATTR_TEMPERATURE))

        self.schedule_update_ha_state()

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            self.vera_device.turn_off()
        elif hvac_mode == HVACMode.HEAT_COOL:
            self.vera_device.turn_auto_on()
        elif hvac_mode == HVACMode.COOL:
            self.vera_device.turn_cool_on()
        elif hvac_mode == HVACMode.HEAT:
            self.vera_device.turn_heat_on()

        self.schedule_update_ha_state()
