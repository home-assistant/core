"""Support for Vera thermostats."""
from __future__ import annotations

from typing import Any

import pyvera as veraApi

from homeassistant.components.climate import (
    DOMAIN as PLATFORM_DOMAIN,
    ENTITY_ID_FORMAT,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_ON,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import convert

from . import VeraDevice
from .common import ControllerData, get_controller_data

FAN_OPERATION_LIST = [FAN_ON, FAN_AUTO]

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE
SUPPORT_HVAC = [HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_HEAT_COOL, HVAC_MODE_OFF]


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
            for device in controller_data.devices.get(PLATFORM_DOMAIN)
        ],
        True,
    )


class VeraThermostat(VeraDevice[veraApi.VeraThermostat], ClimateEntity):
    """Representation of a Vera Thermostat."""

    def __init__(
        self, vera_device: veraApi.VeraThermostat, controller_data: ControllerData
    ):
        """Initialize the Vera device."""
        VeraDevice.__init__(self, vera_device, controller_data)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    @property
    def supported_features(self) -> int | None:
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        mode = self.vera_device.get_hvac_mode()
        if mode == "HeatOn":
            return HVAC_MODE_HEAT
        if mode == "CoolOn":
            return HVAC_MODE_COOL
        if mode == "AutoChangeOver":
            return HVAC_MODE_HEAT_COOL
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return SUPPORT_HVAC

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        mode = self.vera_device.get_fan_mode()
        if mode == "ContinuousOn":
            return FAN_ON
        return FAN_AUTO

    @property
    def fan_modes(self) -> list[str] | None:
        """Return a list of available fan modes."""
        return FAN_OPERATION_LIST

    def set_fan_mode(self, fan_mode) -> None:
        """Set new target temperature."""
        if fan_mode == FAN_ON:
            self.vera_device.fan_on()
        else:
            self.vera_device.fan_auto()

        self.schedule_update_ha_state()

    @property
    def current_power_w(self) -> float | None:
        """Return the current power usage in W."""
        power = self.vera_device.power
        if power:
            return convert(power, float, 0.0)

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        vera_temp_units = self.vera_device.vera_controller.temperature_units

        if vera_temp_units == "F":
            return TEMP_FAHRENHEIT

        return TEMP_CELSIUS

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

    def set_hvac_mode(self, hvac_mode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_OFF:
            self.vera_device.turn_off()
        elif hvac_mode == HVAC_MODE_HEAT_COOL:
            self.vera_device.turn_auto_on()
        elif hvac_mode == HVAC_MODE_COOL:
            self.vera_device.turn_cool_on()
        elif hvac_mode == HVAC_MODE_HEAT:
            self.vera_device.turn_heat_on()

        self.schedule_update_ha_state()
