"""
Allows to configure a switch using a 433MHz module via GPIO on a Raspberry Pi.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.rpi_rf/
"""

import logging

from homeassistant.components.switch import SwitchDevice

REQUIREMENTS = ['rpi-rf==0.9.5']

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument, import-error
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Find and return switches controlled by a generic RF device via GPIO."""
    import rpi_rf

    gpio = config.get('gpio')
    if not gpio:
        _LOGGER.error("No GPIO specified")
        return False

    rfdevice = rpi_rf.RFDevice(gpio)

    switches = config.get('switches', {})
    devices = []
    for dev_name, properties in switches.items():
        if not properties.get('code_on'):
            _LOGGER.error("%s: code_on not specified", dev_name)
            continue
        if not properties.get('code_off'):
            _LOGGER.error("%s: code_off not specified", dev_name)
            continue

        devices.append(
            RPiRFSwitch(
                hass,
                properties.get('name', dev_name),
                rfdevice,
                properties.get('protocol', None),
                properties.get('pulselength', None),
                properties.get('code_on'),
                properties.get('code_off')))
    if devices:
        rfdevice.enable_tx()

    add_devices_callback(devices)


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
        _LOGGER.info('Sending code: %s', code)
        res = self._rfdevice.tx_code(code, protocol, pulselength)
        if not res:
            _LOGGER.error('Sending code %s failed', code)
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
