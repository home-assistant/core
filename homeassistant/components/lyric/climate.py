#  -*- coding:utf-8 -*-

"""
Support for Honeywell Lyric thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.lyric/
"""

import logging

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    FAN_AUTO,
    FAN_DIFFUSE,
    FAN_ON,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.components.lyric import DATA_LYRIC, DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_SCAN_INTERVAL,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ["lyric"]
_LOGGER = logging.getLogger(__name__)

SERVICE_RESUME_PROGRAM = "lyric_resume_program"
SERVICE_RESET_AWAY = "lyric_reset_away"
STATE_HEAT_COOL = "heat-cool"
HOLD_NO_HOLD = "NoHold"
HOLD_HOLD = "Hold"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=1))}
)

RESUME_PROGRAM_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Lyric thermostat."""

    if discovery_info is None:
        return

    _LOGGER.debug("climate discovery_info: %s" % discovery_info)
    _LOGGER.debug("climate config: %s" % config)

    _LOGGER.debug("Set up Lyric climate platform")

    devices = [
        LyricThermostat(device) for _, device in hass.data[DATA_LYRIC].thermostats()
    ]

    add_devices(devices, True)

    def resume_program_service(service):
        """Resume the program on the target thermostats."""

        entity_id = service.data.get(ATTR_ENTITY_ID)

        _LOGGER.debug("resume_program_service entity_id: %s" % entity_id)

        if entity_id:
            target_thermostats = [
                device for device in devices if device.entity_id in entity_id
            ]
        else:
            target_thermostats = devices

        for thermostat in target_thermostats:
            thermostat.thermostatSetpointStatus = HOLD_NO_HOLD
            thermostat.away_override = False

    hass.services.register(
        DOMAIN,
        SERVICE_RESUME_PROGRAM,
        resume_program_service,
        schema=RESUME_PROGRAM_SCHEMA,
    )


class LyricThermostat(ClimateDevice):
    """Representation of a Lyric thermostat."""

    def __init__(self, device):
        """Configure Lyric Thermostat."""

        self.device = device

        self._hvac_possible_modes = {
            "heat": HVAC_MODE_HEAT,
            "emergencyheat": HVAC_MODE_HEAT,
            "off": HVAC_MODE_OFF,
            "cool": HVAC_MODE_COOL,
            "auto": HVAC_MODE_HEAT_COOL,
            "fan": HVAC_MODE_FAN_ONLY,
        }

        self._hvac_possible_modes_rev = {
            HVAC_MODE_HEAT: "Heat",
            HVAC_MODE_OFF: "Off",
            HVAC_MODE_COOL: "Cool",
            HVAC_MODE_HEAT_COOL: "Auto",
            HVAC_MODE_FAN_ONLY: "Fan",
        }

        self._hvac_possible_actions = {
            "heat": CURRENT_HVAC_HEAT,
            "off": CURRENT_HVAC_OFF,
            "cool": CURRENT_HVAC_COOL,
            "auto": CURRENT_HVAC_IDLE,
            "equipmentoff": CURRENT_HVAC_OFF,
        }

        self._fan_possible_modes = {
            "on": FAN_ON,
            "auto": FAN_AUTO,
            "circulate": FAN_DIFFUSE,
        }

        self._fan_possible_modes_rev = {
            FAN_ON: "On",
            FAN_AUTO: "Auto",
            FAN_DIFFUSE: "Circulate",
        }

        self.update()

    def update(self):
        """Update all properties."""

        self._name = self.device.name

        if self.device.units == "Celsius":
            self._temperature_unit = TEMP_CELSIUS
        else:
            self._temperature_unit = TEMP_FAHRENHEIT

        self._current_temperature = float(self.device.indoorTemperature)

        self._target_temperature_step = float(1)
        self._max_temp = int(self.device.maxSetpoint)
        self._min_temp = int(self.device.minSetpoint)

        self._hvac_modes = {}

        for key in self.device.allowedModes:
            self._hvac_modes[key.lower()] = self._hvac_possible_modes[key.lower()]

        self._hvac_mode = self._hvac_modes[self.device.operationMode.lower()]

        self._hvac_action = self._hvac_possible_actions[
            self.device.operationStatus["mode"].lower()
        ]

        if self._hvac_mode == HVAC_MODE_HEAT_COOL or self.device.hasDualSetpointStatus:
            self._has_dual_setpoints = True
            self._supported_features = SUPPORT_TARGET_TEMPERATURE_RANGE
            self._target_temperature = None
            self._target_temperature_high = float(self.device.coolSetpoint)
            self._target_temperature_low = float(self.device.heatSetpoint)
        else:
            self._has_dual_setpoints = False
            self._supported_features = SUPPORT_TARGET_TEMPERATURE

            if self._hvac_mode == HVAC_MODE_HEAT:
                self._target_temperature = float(self.device.heatSetpoint)
            else:
                self._target_temperature = float(self.device.coolSetpoint)

            self._target_temperature_high = None
            self._target_temperature_low = None

        self._fan_modes = {}

        for key in self.device.settings["fan"]["allowedModes"]:
            self._fan_modes[key.lower()] = self._fan_possible_modes[key.lower()]

        self._fan_mode = self._fan_modes[self.device.fanMode.lower()]

        self._supported_features |= SUPPORT_FAN_MODE

    @property
    def name(self):
        """Return the name of the lyric, if any."""

        return self._name

    @property
    def temperature_unit(self):
        """Return temperature unit C/F."""

        return self._temperature_unit

    @property
    def current_temperature(self):
        """Return current temperature."""

        return self._current_temperature

    @property
    def target_temperature(self):
        """Return target temperature."""

        return self._target_temperature

    @property
    def target_temperature_high(self):
        """Return target high temperature."""

        return self._target_temperature_high

    @property
    def target_temperature_low(self):
        """Return target low temperature."""

        return self._target_temperature_low

    @property
    def target_temperature_step(self):
        """Return target temperature step."""

        return self._target_temperature_step

    @property
    def max_temp(self):
        """Return max temperature."""

        return self._max_temp

    @property
    def min_temp(self):
        """Return min temperature."""

        return self._min_temp

    @property
    def hvac_mode(self):
        """Return HVAC mode."""

        return self._hvac_mode

    @property
    def hvac_action(self):
        """Return HVAC action."""

        return self._hvac_action

    @property
    def hvac_modes(self):
        """Return HVAC possible  modes."""

        return list(tuple(self._hvac_modes.values()))

    @property
    def fan_mode(self):
        """Return fan mode."""

        return self._fan_mode

    @property
    def fan_modes(self):
        """Return possible fan modes."""

        return list(tuple(self._fan_modes.values()))

    @property
    def supported_features(self):
        """Return supported features."""

        return self._supported_features

    def set_temperature(self, **kwargs):
        """Set new target temperature."""

        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if self._has_dual_setpoints:
            if target_temp_low is not None and target_temp_high is not None:
                if target_temp_high - target_temp_low < 1:
                    target_temp_high = target_temp_low + 1

                temp = (target_temp_high, target_temp_low)
        else:
            temp = kwargs.get(ATTR_TEMPERATURE)

        self.device.thermostatSetpointStatus = "TemporaryHold"
        _LOGGER.debug("Lyric set_temperature-output-value=%s", temp)
        self.device.temperatureSetpoint = temp

    def set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""

        if hvac_mode in self._hvac_possible_modes_rev.keys():
            self.device.thermostatSetpointStatus = "TemporaryHold"
            self.device.mode = self._hvac_possible_modes_rev[hvac_mode]
            _LOGGER.debug(
                "Lyric set_hvac_mode-output-value=%s",
                self._hvac_possible_modes_rev[hvac_mode],
            )
            self.device.operationMode = self._hvac_possible_modes_rev[hvac_mode]

            # Fix dual setpoint to not be the same degree
            if hvac_mode == HVAC_MODE_HEAT_COOL:
                setpoint = self.device.heatSetpoint

                self.device.temperatureSetpoint = (setpoint + 1, setpoint)

    def set_fan_mode(self, fan):
        """Set fan state."""

        if fan in self._fan_possible_modes_rev.keys():
            self.device.thermostatSetpointStatus = "TemporaryHold"
            self.device.fanMode = self._fan_possible_modes_rev[fan]
