"""
Support for Anova sous-vide machines.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/sousvide.anova/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sous_vide import SousVideEntity
from homeassistant.const import (
    CONF_MAC, CONF_NAME, PRECISION_TENTHS, STATE_OFF, STATE_ON, STATE_PROBLEM,
    STATE_UNKNOWN, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa

REQUIREMENTS = ['btlewrap==0.0.2']

_LOGGER = logging.getLogger(__name__)

CHANDLE_ANOVA = 0x25  # BTLE characteristic handle for interacting with Anova.
NOTIFICATION_TIMEOUT = 1.0  # Notification wait timeout in seconds.
DEFAULT_TARGET_TEMP_IN_C = 0
DEFAULT_CURRENT_TEMP_IN_C = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_NAME, default=None): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Perform setup for the platform."""
    import btlewrap

    backends = btlewrap.available_backends()
    if not backends:
        _LOGGER.error('No available Bluetooth backends.')
        return

    backend = backends[0]  # Any available backend works.
    _LOGGER.debug('Using the %s Bluetooth backend.', backend.__name__)

    name = config[CONF_NAME]
    mac = config[CONF_MAC]
    add_devices([AnovaEntity(name, mac, backend)], True)


class AnovaEntity(SousVideEntity):  # pylint: disable=too-many-instance-attributes; # noqa: E501
    """Representation of an Anova sous-vide cooker."""

    _temp = DEFAULT_CURRENT_TEMP_IN_C
    _target_temp = DEFAULT_TARGET_TEMP_IN_C
    _unit = TEMP_CELSIUS
    _state = STATE_UNKNOWN
    _last_notification = None

    def __init__(self, name, mac, backend):
        """Create a new instance of AnovaEntity."""
        from btlewrap.base import BluetoothInterface

        self._name = name
        self._mac = mac
        self._bt_interface = BluetoothInterface(backend)

    @property
    def name(self):
        """Return the name of the cooker."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the cooker."""
        return self._unit

    @property
    def precision(self):
        """Return the precision of the cooker's temperature measurement."""
        # 1/10 of a degree precision is hardcoded in the Anova.
        return PRECISION_TENTHS

    @property
    def current_temperature(self) -> float:
        """Return the cooker's current temperature."""
        return self._temp

    @property
    def target_temperature(self) -> float:
        """Return the cooker's target temperature."""
        return self._target_temp

    @property
    def min_temperature(self) -> float:
        """Return the minimum target temperature of the cooker."""
        # 0C min temp is hardcoded in the Anova.
        return 0

    @property
    def max_temperature(self) -> float:
        """Return the maximum target temperature of the cooker."""
        # 99C max temp is hardcoded in the Anova.
        return 99

    @property
    def is_on(self) -> bool:
        """Return True if the cooker is on."""
        return self._state == STATE_ON

    def turn_on(self, **kwargs) -> None:
        """Turn the cooker on (starts cooking."""
        self.send_btle_command('start')
        self._state = STATE_ON

    def turn_off(self, **kwargs) -> None:
        """Turn the cooker off (stops cooking)."""
        self.send_btle_command('stop')
        self._state = STATE_OFF

    def set_temp(self, temperature=None) -> None:
        """Set the target temperature of the cooker."""
        if temperature is not None:
            self._target_temp = max(
                min(temperature, self.max_temperature), self.min_temperature)
            self.send_btle_command('set temp {}'.format(self._target_temp))

    def update(self):
        """Fetch state from the device."""
        status = self.send_btle_command('status', True)
        if status == 'running':
            self._state = STATE_ON
        elif status == 'stopped':
            self._state = STATE_OFF
        elif status in ('low water', 'heater error', 'power interrupt error'):
            self._state = STATE_PROBLEM
        else:
            self._state = STATE_UNKNOWN

        unit = self.send_btle_command('read unit', True) or ''
        self._unit = TEMP_CELSIUS if unit == 'c' else TEMP_FAHRENHEIT

        self._temp = float(self.send_btle_command('read temp', True) or 0)
        self._target_temp = float(
            self.send_btle_command('read set temp', True) or 0)

    def send_btle_command(self, command, read_response=False):
        """Send a BTLE command."""
        from btlewrap.base import BluetoothBackendException

        _LOGGER.debug("Sending command %s", command)
        command = "{0}\r".format(command)
        try:
            with self._bt_interface.connect(self._mac) as conn:
                conn.write_handle(  # pylint: disable=no-member
                    CHANDLE_ANOVA, bytes(command, 'UTF-8'))
                if read_response:
                    _LOGGER.debug("Waiting for response")
                    if conn.wait_for_notification(  # pylint: disable=no-member
                            CHANDLE_ANOVA, self, NOTIFICATION_TIMEOUT):
                        _LOGGER.debug("Got response: %s",
                                      self._last_notification)
                        return self._last_notification
        except BluetoothBackendException:
            _LOGGER.debug('Command failed, couldnt connect')
            return None
        return None

    def handleNotification(self, handle, raw_data):  # pylint: disable=invalid-name; # noqa: E501
        """Callback to handle BTLE notifications."""
        if raw_data is None:
            return

        self._last_notification = raw_data.strip().decode("UTF-8")
