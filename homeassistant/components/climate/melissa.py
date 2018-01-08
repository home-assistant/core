"""
Support for Melissa Climate A/C.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.melissa/
"""
import logging

from homeassistant.components.climate import ClimateDevice, \
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE, SUPPORT_ON_OFF, \
    STATE_AUTO, STATE_HEAT, STATE_COOL, STATE_DRY, STATE_FAN_ONLY, \
    SUPPORT_FAN_MODE
from homeassistant.components.fan import SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH
from homeassistant.components.melissa import DATA_MELISSA, DOMAIN, \
    CHANGE_THRESHOLD
from homeassistant.const import TEMP_CELSIUS, STATE_ON, STATE_OFF, \
    STATE_UNKNOWN, STATE_IDLE, ATTR_TEMPERATURE

DEPENDENCIES = [DOMAIN]

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE | \
                SUPPORT_ON_OFF | SUPPORT_FAN_MODE


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Iterate through all MAX! Devices and add thermostats."""
    connection = hass.data[DATA_MELISSA]
    devices = connection.fetch_devices()

    all_devices = []

    for device in devices.values():
        name = 'Melissa {} {}'.format(device['type'], device['serial_number'])

        all_devices.append(MelissaClimate(
            connection, name, device['serial_number'], device))

    if all_devices:
        add_devices(all_devices)


class MelissaClimate(ClimateDevice):
    """Representation of a Melissa Climate."""

    def __init__(self, connection, name, serial_number, init_data):
        """Initialize the climate device."""
        self._name = name
        self._connection = connection
        self._serial_number = serial_number
        self._data = init_data['controller_log']
        self._state = None
        self._cur_settings = self._connection.cur_settings(
            serial_number
        )['controller']['_relation']['command_log']
        self._latest_temp = None

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def is_on(self):
        """Return current state."""
        from melissa import STATE, STATE_ON as ON, STATE_IDLE as IDLE
        return self._cur_settings[STATE] in (ON, IDLE)

    @property
    def current_fan_mode(self):
        """Return the current fan mode."""
        from melissa import FAN
        return self.melissa_fan_to_hass(self._cur_settings[FAN])

    @property
    def current_temperature(self):
        """Return the current temperature."""
        from melissa import TEMP
        if not self._latest_temp or abs(
                self._latest_temp - self._data[TEMP]) < CHANGE_THRESHOLD:
            self._latest_temp = self._data[TEMP]
        return self._latest_temp

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def current_operation(self):
        """Return the current operation mode."""
        from melissa import MODE
        return self.melissa_op_to_hass(self._cur_settings[MODE])

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return [
            STATE_AUTO, STATE_HEAT, STATE_COOL, STATE_DRY, STATE_FAN_ONLY
        ]

    @property
    def fan_list(self):
        """List of available fan modes."""
        return [
            STATE_AUTO, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH
        ]

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        from melissa import TEMP
        return self._cur_settings[TEMP]

    @property
    def state(self):
        """Return current state."""
        from melissa import STATE
        return self.melissa_state_to_hass(self._cur_settings[STATE])

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def min_temp(self):
        """Return the minimum supported temperature for the thermostat."""
        return 16

    @property
    def max_temp(self):
        """Return the maximum supported temperature for the thermostat."""
        return 30

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        from melissa import TEMP
        temp = kwargs.get(ATTR_TEMPERATURE)
        return self.send({TEMP: temp})

    def set_fan_mode(self, fan):
        """Set fan mode."""
        from melissa import FAN
        fan_mode = self.hass_fan_to_melissa(fan)
        return self.send({FAN: fan_mode})

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        from melissa import MODE
        mode = self.hass_mode_to_melissa(operation_mode)
        return self.send({MODE: mode})

    def turn_on(self):
        """Turn on device."""
        from melissa import STATE, STATE_ON as ON  # pylint: disable=W0621
        return self.send({STATE: ON})

    def turn_off(self):
        """Turn off device."""
        from melissa import STATE, STATE_OFF as OFF  # pylint: disable=W0621
        return self.send({STATE: OFF})

    def send(self, value):
        """Sending action to service"""
        old_value = self._cur_settings.copy()
        self._cur_settings.update(value)
        if not self._connection.send(self._serial_number, self._cur_settings):
            self._cur_settings = old_value
            return False
        else:
            return True

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    def update(self):
        """Get latest data from Melissa."""
        self._data = self._connection.status()[self._serial_number]

    @staticmethod
    def melissa_state_to_hass(state):
        """Translate Melissa states to hass states."""
        from melissa import STATE_ON as ON, \
            STATE_OFF as OFF, STATE_IDLE as IDLE
        if state == ON:
            return STATE_ON
        elif state == OFF:
            return STATE_OFF
        elif state == IDLE:
            return STATE_IDLE
        else:
            return STATE_UNKNOWN

    @staticmethod
    def melissa_op_to_hass(mode):
        """Translate Melissa modes to hass states."""
        from melissa import MODE_HEAT, MODE_AUTO, MODE_COOL, MODE_DRY, MODE_FAN
        if mode == MODE_AUTO:
            return STATE_AUTO
        elif mode == MODE_HEAT:
            return STATE_HEAT
        elif mode == MODE_COOL:
            return STATE_COOL
        elif mode == MODE_DRY:
            return STATE_DRY
        elif mode == MODE_FAN:
            return STATE_FAN_ONLY
        else:
            return STATE_UNKNOWN

    @staticmethod
    def melissa_fan_to_hass(fan):
        """Translate Melissa fan modes to hass modes."""
        from melissa import FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH
        if fan == FAN_AUTO:
            return STATE_AUTO
        elif fan == FAN_LOW:
            return SPEED_LOW
        elif fan == FAN_MEDIUM:
            return SPEED_MEDIUM
        elif fan == FAN_HIGH:
            return SPEED_HIGH
        else:
            return STATE_UNKNOWN

    @staticmethod
    def hass_mode_to_melissa(mode):
        """Translate hass states to melissa modes."""
        from melissa import MODE_HEAT, MODE_AUTO, MODE_COOL, MODE_DRY, MODE_FAN
        if mode == STATE_AUTO:
            return MODE_AUTO
        elif mode == STATE_HEAT:
            return MODE_HEAT
        elif mode == STATE_COOL:
            return MODE_COOL
        elif mode == STATE_DRY:
            return MODE_DRY
        elif mode == STATE_FAN_ONLY:
            return MODE_FAN

    @staticmethod
    def hass_fan_to_melissa(fan):
        """Translate hass fan modes to melissa modes."""
        from melissa import FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH
        if fan == STATE_AUTO:
            return FAN_AUTO
        elif fan == SPEED_LOW:
            return FAN_LOW
        elif fan == SPEED_MEDIUM:
            return FAN_MEDIUM
        elif fan == SPEED_HIGH:
            return FAN_HIGH
