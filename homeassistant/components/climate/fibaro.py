"""
Support for Fibaro thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.fibaro/
"""
import logging

from homeassistant.components.climate import (
    ClimateDevice, STATE_AUTO, STATE_COOL,
    STATE_HEAT, STATE_FAN_ONLY, ENTITY_ID_FORMAT,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_OPERATION_MODE, SUPPORT_FAN_MODE)
from homeassistant.const import (
    STATE_ON,
    STATE_OFF,
    TEMP_FAHRENHEIT,
    TEMP_CELSIUS,
    ATTR_TEMPERATURE)

from homeassistant.components.fibaro import (
    FIBARO_DEVICES, FibaroDevice)

SPEED_LOW = 'low'
SPEED_MEDIUM = 'medium'
SPEED_HIGH = 'high'
DEPENDENCIES = ['fibaro']

_LOGGER = logging.getLogger(__name__)


FANMODE_MAP = {
    "1": {0: STATE_OFF, 1: STATE_ON},
    "1,128": {0: STATE_OFF, 1: STATE_ON, 128: STATE_AUTO},
    "1,3,5,128": {0: STATE_OFF, 1: SPEED_LOW, 3: SPEED_MEDIUM,
                  5: SPEED_HIGH, 128: STATE_AUTO},
}

IFANMODE_MAP = {
    "1": {STATE_OFF: 0, STATE_ON: 1},
    "1,128": {STATE_OFF: 0, STATE_ON: 1, STATE_AUTO: 128},
    "1,3,5,128": {STATE_OFF: 0, SPEED_LOW: 1, SPEED_MEDIUM: 3,
                  SPEED_HIGH: 5, STATE_AUTO: 128},
}

OPMODE_MAP = {
    "0,1": {0: STATE_OFF, 1: STATE_ON},
    "0,1,2": {0: STATE_OFF, 1: STATE_HEAT, 2: STATE_COOL},
    "0,1,2,6": {0: STATE_OFF, 1: STATE_HEAT, 2: STATE_COOL,
                6: STATE_FAN_ONLY},
}

IOPMODE_MAP = {
    "0,1": {STATE_OFF: 0, STATE_ON: 1},
    "0,1,2": {STATE_OFF: 0, STATE_HEAT: 1, STATE_COOL: 2},
    "0,1,2,6": {STATE_OFF: 0, STATE_HEAT: 1, STATE_COOL: 2,
                STATE_FAN_ONLY: 6},
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
    """Representation of a Vera Thermostat."""

    def __init__(self, fibaro_device):
        """Initialize the Vera device."""
        super().__init__(fibaro_device)
        self._tempsensor_device = None
        self._targettemp_device = None
        self._opmode_device = None
        self._fanmode_device = None
        self._support_flags = 0
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

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
            elif device.type == 'com.fibaro.setPoint' or\
                    device.type == 'com.fibaro.thermostatDanfoss':
                self._targettemp_device = FibaroDevice(device)
                self._support_flags |= SUPPORT_TARGET_TEMPERATURE
                tempunit = device.properties.unit
            elif device.type == 'com.fibaro.operatingMode':
                self._opmode_device = FibaroDevice(device)
                self._support_flags |= SUPPORT_OPERATION_MODE
            elif device.type == 'com.fibaro.fanMode':
                self._fanmode_device = FibaroDevice(device)
                self._support_flags |= SUPPORT_FAN_MODE

        if tempunit == 'F':
            self._unit_of_temp = TEMP_FAHRENHEIT
        else:
            self._unit_of_temp = TEMP_CELSIUS

        if self._fanmode_device:
            smode = self._fanmode_device.fibaro_device.\
                properties.supportedModes
            self._fanmode_map = FANMODE_MAP.get(smode, {})
            self._ifanmode_map = IFANMODE_MAP.get(smode, {})
        if self._opmode_device:
            omode = self._opmode_device.fibaro_device.\
                properties.supportedModes
            self._opmode_map = OPMODE_MAP.get(omode, {})
            self._iopmode_map = IOPMODE_MAP.get(omode, {})

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
