"""
Support for Fibaro thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.fibaro/
"""
import logging

from homeassistant.components.climate import (
    ClimateDevice, STATE_AUTO, STATE_COOL,
    STATE_DRY, STATE_FAN_ONLY, STATE_HEAT,
    ENTITY_ID_FORMAT,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_OPERATION_MODE, SUPPORT_FAN_MODE)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_OFF,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT)

from homeassistant.components.fibaro import (
    FIBARO_DEVICES, FibaroDevice)

SPEED_LOW = 'low'
SPEED_MEDIUM = 'medium'
SPEED_HIGH = 'high'
STATE_AUXILIARY = 'auxiliary'
STATE_RESUME = 'resume'
STATE_MOIST = 'moist'
STATE_AUTO_CHANGEOVER = 'auto changeover'
STATE_ENERGY_HEAT = 'energy heat'
STATE_ENERGY_COOL = 'energy cool'
STATE_FULL_POWER = 'full power'
STATE_FORCE_OPEN = 'force open'
STATE_AWAY = 'away'
FAN_AUTO_HIGH = 'auto_high'
FAN_AUTO_MEDIUM = 'auto_medium'
FAN_CIRCULATION = 'circulation'
FAN_HUMIDITY_CIRCULATION = 'humidity_circulation'
FAN_LEFT_RIGHT = 'left_right'
FAN_UP_DOWN = 'up_down'
FAN_QUIET = 'quiet'
STATE_FURNACE = 'furnace'

DEPENDENCIES = ['fibaro']

_LOGGER = logging.getLogger(__name__)

# SDS13781-10 Z-Wave Application Command Class Specification 2019-01-04
# Table 128, Thermostat Fan Mode Set version 4::Fan Mode encoding
FANMODES = {
    0: STATE_OFF,
    1: SPEED_LOW,
    2: FAN_AUTO_HIGH,
    3: SPEED_HIGH,
    4: FAN_AUTO_MEDIUM,
    5: SPEED_MEDIUM,
    6: FAN_CIRCULATION,
    7: FAN_HUMIDITY_CIRCULATION,
    8: FAN_LEFT_RIGHT,
    9: FAN_UP_DOWN,
    10: FAN_QUIET,
    128: STATE_AUTO
}

# SDS13781-10 Z-Wave Application Command Class Specification 2019-01-04
# Table 130, Thermostat Mode Set version 3::Mode encoding.
OPMODES = {
    0: STATE_OFF,
    1: STATE_HEAT,
    2: STATE_COOL,
    3: STATE_AUTO,
    4: STATE_AUXILIARY,
    5: STATE_RESUME,
    6: STATE_FAN_ONLY,
    7: STATE_FURNACE,
    8: STATE_DRY,
    9: STATE_MOIST,
    10: STATE_AUTO_CHANGEOVER,
    11: STATE_ENERGY_HEAT,
    12: STATE_ENERGY_COOL,
    13: STATE_AWAY,
    15: STATE_FULL_POWER,
    31: STATE_FORCE_OPEN
}

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for Fibaro controller devices."""
    if discovery_info is None:
        return

    add_entities(
        [FibaroThermostat(device)
         for device in hass.data[FIBARO_DEVICES]['climate']], True)


class FibaroThermostat(FibaroDevice, ClimateDevice):
    """Representation of a Fibaro Thermostat."""

    def __init__(self, fibaro_device):
        """Initialize the Fibaro device."""
        super().__init__(fibaro_device)
        self._tempsensor_device = None
        self._targettemp_device = None
        self._opmode_device = None
        self._fanmode_device = None
        self._support_flags = 0
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)
        self._fanmode_map = {}
        self._ifanmode_map = {}
        self._opmode_map = {}
        self._iopmode_map = {}

        siblings = fibaro_device.fibaro_controller.get_siblings(
            fibaro_device.id)
        tempunit = 'C'
        for device in siblings:
            if device != fibaro_device:
                self.controller.register(device.id,
                                         self._update_callback)
            if device.type == 'com.fibaro.temperatureSensor':
                self._tempsensor_device = FibaroDevice(device)
                tempunit = device.properties.unit
            if 'setTargetLevel' in device.actions:
                self._targettemp_device = FibaroDevice(device)
                self._support_flags |= SUPPORT_TARGET_TEMPERATURE
                tempunit = device.properties.unit
            if 'setMode' in device.actions:
                self._opmode_device = FibaroDevice(device)
                self._support_flags |= SUPPORT_OPERATION_MODE
            if 'setFanMode' in device.actions:
                self._fanmode_device = FibaroDevice(device)
                self._support_flags |= SUPPORT_FAN_MODE

        if tempunit == 'F':
            self._unit_of_temp = TEMP_FAHRENHEIT
        else:
            self._unit_of_temp = TEMP_CELSIUS

        if self._fanmode_device:
            smode = self._fanmode_device.fibaro_device.\
                properties.supportedModes.split(",")
            for mode in smode:
                try:
                    self._fanmode_map[int(mode)] = FANMODES[int(mode)]
                    self._ifanmode_map[FANMODES[int(mode)]] = int(mode)
                except KeyError:
                    self._fanmode_map[int(mode)] = 'unkown'

        if self._opmode_device:
            prop = self._opmode_device.fibaro_device.properties
            if "supportedOperatingModes" in prop:
                omode = prop.supportedOperatingModes.split(",")
            elif "supportedModes" in prop:
                omode = prop.supportedModes.split(",")
            for mode in omode:
                try:
                    self._opmode_map[int(mode)] = OPMODES[int(mode)]
                    self._iopmode_map[OPMODES[int(mode)]] = int(mode)
                except KeyError:
                    self._opmode_map[int(mode)] = 'unkown'

        _LOGGER.debug("Climate %s", self.ha_id)
        _LOGGER.debug("- _tempsensor_device %s", self._tempsensor_device.ha_id
                      if self._tempsensor_device else "None")
        _LOGGER.debug("- _targettemp_device %s", self._targettemp_device.ha_id
                      if self._targettemp_device else "None")
        _LOGGER.debug("- _opmode_device %s", self._opmode_device.ha_id
                      if self._opmode_device else "None")
        _LOGGER.debug("- _fanmode_device %s", self._fanmode_device.ha_id
                      if self._fanmode_device else "None")

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        if self._fanmode_device is None:
            return None
        return [k for k in self._fanmode_map.values()]

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        if self._fanmode_device is None:
            return None

        mode = int(self._fanmode_device.fibaro_device.properties.mode)
        return self._fanmode_map[mode]

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if self._fanmode_device is None:
            return
        self._fanmode_device.action("setFanMode", self._ifanmode_map[fan_mode])

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if self._opmode_device is None:
            return None

        if "operatingMode" in self._opmode_device.fibaro_device.properties:
            mode = int(self._opmode_device.fibaro_device.
                       properties.operatingMode)
        else:
            mode = int(self._opmode_device.fibaro_device.properties.mode)
        ret = self._opmode_map.get(mode, "")
        return ret

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        if self._opmode_device is None:
            return None
        ret = [k for k in self._opmode_map.values()]
        return ret

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        if self._opmode_device is None:
            return
        if "setOperatingMode" in self._opmode_device.fibaro_device.actions:
            self._opmode_device.action("setOperatingMode",
                                       self._iopmode_map[operation_mode])
        elif "setMode" in self._opmode_device.fibaro_device.actions:
            self._opmode_device.action("setMode",
                                       self._iopmode_map[operation_mode])

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_temp

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._tempsensor_device:
            device = self._tempsensor_device.fibaro_device
            return float(device.properties.value)
        return None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._targettemp_device:
            device = self._targettemp_device.fibaro_device
            return float(device.properties.targetLevel)
        return None

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._targettemp_device.action("setTargetLevel",
                                           kwargs.get(ATTR_TEMPERATURE))

    @property
    def is_on(self):
        """Return true if on."""
        if self.current_operation == STATE_OFF:
            return False
        return True

    def update(self):
        """Update the state."""
        pass
