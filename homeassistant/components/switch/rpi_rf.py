"""
Allows to configure a switch using a 433MHz module via GPIO on a Raspberry Pi.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.rpi_rf/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_NAME, CONF_SWITCHES)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['rpi-rf==0.9.5']

_LOGGER = logging.getLogger(__name__)

CONF_CODE_OFF = 'code_off'
CONF_CODE_ON = 'code_on'
CONF_GPIO = 'gpio'
CONF_PROTOCOL = 'protocol'
CONF_PULSELENGTH = 'pulselength'

DEFAULT_PROTOCOL = 1

SWITCH_SCHEMA = vol.Schema({
    vol.Required(CONF_CODE_OFF): cv.positive_int,
    vol.Required(CONF_CODE_ON): cv.positive_int,
    vol.Optional(CONF_PULSELENGTH): cv.positive_int,
    vol.Optional(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): cv.positive_int,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_GPIO): cv.positive_int,
    vol.Required(CONF_SWITCHES): vol.Schema({cv.string: SWITCH_SCHEMA}),
})


# pylint: disable=unused-argument, import-error
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return switches controlled by a generic RF device via GPIO."""
    import rpi_rf

    gpio = config.get(CONF_GPIO)
    rfdevice = rpi_rf.RFDevice(gpio)
    switches = config.get(CONF_SWITCHES)

    devices = []
    for dev_name, properties in switches.items():
        devices.append(
            RPiRFSwitch(
                hass,
                properties.get(CONF_NAME, dev_name),
                rfdevice,
                properties.get(CONF_PROTOCOL),
                properties.get(CONF_PULSELENGTH),
                properties.get(CONF_CODE_ON),
                properties.get(CONF_CODE_OFF)
            )
        )
    if devices:
        rfdevice.enable_tx()

    add_devices(devices)


class RPiRFSwitch(SwitchDevice):
    """Representation of a GPIO RF switch."""

    # pylint: disable=too-many-arguments, too-many-instance-attributes
    def __init__(self, hass, name, rfdevice, protocol, pulselength,
                 code_on, code_off):
        """Initialize the switch."""
        self._hass = hass
        self._name = name
        self._state = False
        self._rfdevice = rfdevice
        self._protocol = protocol
        self._pulselength = pulselength
        self._code_on = code_on
        self._code_off = code_off

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

    def _send_code(self, code, protocol, pulselength):
        """Send the code with a specified pulselength."""
        _LOGGER.info("Sending code: %s", code)
        res = self._rfdevice.tx_code(code, protocol, pulselength)
        if not res:
            _LOGGER.error("Sending code %s failed", code)
        return res

    def turn_on(self):
        """Turn the switch on."""
        if self._send_code(self._code_on, self._protocol, self._pulselength):
            self._state = True
            self.update_ha_state()

    def turn_off(self):
        """Turn the switch off."""
        if self._send_code(self._code_off, self._protocol, self._pulselength):
            self._state = False
            self.update_ha_state()
