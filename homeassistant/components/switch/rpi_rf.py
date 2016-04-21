"""
Allows to configure a switch using a 433MHz module via GPIO on a Raspberry Pi.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.rpi_rf/
"""

import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import CONF_VALUE_TEMPLATE

DEFAULT_PULSELENGTH = 350

REQUIREMENTS = ['RPi.GPIO==0.6.2', 'rpi-rf==0.9.4']

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Find and return switches controlled by a generic RF device via GPIO."""
    import rpi_rf

    gpio = config.get('gpio', 17)
    rfdevice = rpi_rf.RFDevice(gpio)

    switches = config.get('switches', {})
    devices = []
    for dev_name, properties in switches.items():
        devices.append(
            RPiRFSwitch(
                hass,
                properties.get('name', dev_name),
                rfdevice,
                properties.get('pulselength', DEFAULT_PULSELENGTH),
                properties.get('code_on', 0),
                properties.get('code_off', 0),
                properties.get(CONF_VALUE_TEMPLATE, False)))
    add_devices_callback(devices)


class RPiRFSwitch(SwitchDevice):
    """Representation of a GPIO RF switch."""

    # pylint: disable=too-many-arguments, too-many-instance-attributes
    def __init__(self, hass, name, rfdevice, pulselength, code_on, code_off,
                 value_template):
        """Initialize the switch."""
        self._hass = hass
        self._name = name
        self._state = False
        self._rfdevice = rfdevice
        self._pulselength = pulselength
        self._code_on = code_on
        self._code_off = code_off
        self._value_template = value_template

        rfdevice.enable_tx()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def _send_code(self, code, pulselength):
        """Send the code with a specified pulselength."""
        _LOGGER.info('Sending code: %s (%s)', code, pulselength)
        self._rfdevice.tx_pulselength = pulselength
        res = self._rfdevice.tx_code(code)
        if not res:
            _LOGGER.error('Sending code %s failed', code)
        return res

    def turn_on(self):
        """Turn the switch on."""
        if self._send_code(self._code_on, self._pulselength):
            self._state = True
            self.update_ha_state()

    def turn_off(self):
        """Turn the switch off."""
        if self._send_code(self._code_off, self._pulselength):
            self._state = False
            self.update_ha_state()
