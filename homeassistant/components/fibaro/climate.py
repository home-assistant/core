"""Support for Fibaro thermostats."""
import logging

from homeassistant.components.climate.const import (
    STATE_AUTO, STATE_COOL, STATE_DRY,
    STATE_ECO, STATE_FAN_ONLY, STATE_HEAT,
    STATE_MANUAL, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_OPERATION_MODE, SUPPORT_FAN_MODE)

from homeassistant.components.climate import (
    ClimateDevice)

from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_OFF,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT)

from . import (
    FIBARO_DEVICES, FibaroDevice)

SPEED_LOW = 'low'
SPEED_MEDIUM = 'medium'
SPEED_HIGH = 'high'

# State definitions missing from HA, but defined by Z-Wave standard.
# We map them to states known supported by HA here:
STATE_AUXILIARY = STATE_HEAT
STATE_RESUME = STATE_HEAT
STATE_MOIST = STATE_DRY
STATE_AUTO_CHANGEOVER = STATE_AUTO
STATE_ENERGY_HEAT = STATE_ECO
STATE_ENERGY_COOL = STATE_COOL
STATE_FULL_POWER = STATE_AUTO
STATE_FORCE_OPEN = STATE_MANUAL
STATE_AWAY = STATE_AUTO
STATE_FURNACE = STATE_HEAT

FAN_AUTO_HIGH = 'auto_high'
FAN_AUTO_MEDIUM = 'auto_medium'
FAN_CIRCULATION = 'circulation'
FAN_HUMIDITY_CIRCULATION = 'humidity_circulation'
FAN_LEFT_RIGHT = 'left_right'
FAN_UP_DOWN = 'up_down'
FAN_QUIET = 'quiet'

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
        self._temp_sensor_device = None
        self._target_temp_device = None
        self._op_mode_device = None
        self._fan_mode_device = None
        self._support_flags = 0
        self.entity_id = 'climate.{}'.format(self.ha_id)
        self._fan_mode_to_state = {}
        self._fan_state_to_mode = {}
        self._op_mode_to_state = {}
        self._op_state_to_mode = {}

        siblings = fibaro_device.fibaro_controller.get_siblings(
            fibaro_device.id)
        tempunit = 'C'
        for device in siblings:
            if device.type == 'com.fibaro.temperatureSensor':
                self._temp_sensor_device = FibaroDevice(device)
                tempunit = device.properties.unit
            if 'setTargetLevel' in device.actions or \
                    'setThermostatSetpoint' in device.actions:
                self._target_temp_device = FibaroDevice(device)
                self._support_flags |= SUPPORT_TARGET_TEMPERATURE
                tempunit = device.properties.unit
            if 'setMode' in device.actions or \
                    'setOperatingMode' in device.actions:
                self._op_mode_device = FibaroDevice(device)
                self._support_flags |= SUPPORT_OPERATION_MODE
            if 'setFanMode' in device.actions:
                self._fan_mode_device = FibaroDevice(device)
                self._support_flags |= SUPPORT_FAN_MODE

        if tempunit == 'F':
            self._unit_of_temp = TEMP_FAHRENHEIT
        else:
            self._unit_of_temp = TEMP_CELSIUS

        if self._fan_mode_device:
            fan_modes = self._fan_mode_device.fibaro_device.\
                properties.supportedModes.split(",")
            for mode in fan_modes:
                try:
                    self._fan_mode_to_state[int(mode)] = FANMODES[int(mode)]
                    self._fan_state_to_mode[FANMODES[int(mode)]] = int(mode)
                except KeyError:
                    self._fan_mode_to_state[int(mode)] = 'unknown'

        if self._op_mode_device:
            prop = self._op_mode_device.fibaro_device.properties
            if "supportedOperatingModes" in prop:
                op_modes = prop.supportedOperatingModes.split(",")
            elif "supportedModes" in prop:
                op_modes = prop.supportedModes.split(",")
            for mode in op_modes:
                try:
                    self._op_mode_to_state[int(mode)] = OPMODES[int(mode)]
                    self._op_state_to_mode[OPMODES[int(mode)]] = int(mode)
                except KeyError:
                    self._op_mode_to_state[int(mode)] = 'unknown'

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        _LOGGER.debug("Climate %s\n"
                      "- _temp_sensor_device %s\n"
                      "- _target_temp_device %s\n"
                      "- _op_mode_device %s\n"
                      "- _fan_mode_device %s",
                      self.ha_id,
                      self._temp_sensor_device.ha_id
                      if self._temp_sensor_device else "None",
                      self._target_temp_device.ha_id
                      if self._target_temp_device else "None",
                      self._op_mode_device.ha_id
                      if self._op_mode_device else "None",
                      self._fan_mode_device.ha_id
                      if self._fan_mode_device else "None")
        await super().async_added_to_hass()

        # Register update callback for child devices
        siblings = self.fibaro_device.fibaro_controller.get_siblings(
            self.fibaro_device.id)
        for device in siblings:
            if device != self.fibaro_device:
                self.controller.register(device.id,
                                         self._update_callback)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        if self._fan_mode_device is None:
            return None
        return list(self._fan_state_to_mode)

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        if self._fan_mode_device is None:
            return None

        mode = int(self._fan_mode_device.fibaro_device.properties.mode)
        return self._fan_mode_to_state[mode]

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if self._fan_mode_device is None:
            return
        self._fan_mode_device.action(
            "setFanMode", self._fan_state_to_mode[fan_mode])

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if self._op_mode_device is None:
            return None

        if "operatingMode" in self._op_mode_device.fibaro_device.properties:
            mode = int(self._op_mode_device.fibaro_device.
                       properties.operatingMode)
        else:
            mode = int(self._op_mode_device.fibaro_device.properties.mode)
        return self._op_mode_to_state.get(mode)

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        if self._op_mode_device is None:
            return None
        return list(self._op_state_to_mode)

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        if self._op_mode_device is None:
            return
        if "setOperatingMode" in self._op_mode_device.fibaro_device.actions:
            self._op_mode_device.action(
                "setOperatingMode", self._op_state_to_mode[operation_mode])
        elif "setMode" in self._op_mode_device.fibaro_device.actions:
            self._op_mode_device.action(
                "setMode", self._op_state_to_mode[operation_mode])

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_temp

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._temp_sensor_device:
            device = self._temp_sensor_device.fibaro_device
            return float(device.properties.value)
        return None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._target_temp_device:
            device = self._target_temp_device.fibaro_device
            return float(device.properties.targetLevel)
        return None

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        target = self._target_temp_device
        if temperature is not None:
            if "setThermostatSetpoint" in target.fibaro_device.actions:
                target.action("setThermostatSetpoint",
                              self._op_state_to_mode[self.current_operation],
                              temperature)
            else:
                target.action("setTargetLevel",
                              temperature)

    @property
    def is_on(self):
        """Return true if on."""
        if self.current_operation == STATE_OFF:
            return False
        return True
