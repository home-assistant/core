"""Support for Lutron Caseta switches."""
import logging

from homeassistant.components.lutron_caseta import LUTRON_CASETA_DEVICES
from homeassistant.components.lutron_caseta import LUTRON_CASETA_SMARTBRIDGE
from homeassistant.components.lutron_caseta import LutronCasetaDevice
from homeassistant.components.switch import SwitchDevice


_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Lutron switch."""
    devs = []
    for device in hass.data[LUTRON_CASETA_DEVICES]['switch']:
        dev = LutronCasetaLight(device,
                                hass.data[LUTRON_CASETA_SMARTBRIDGE])
        devs.append(dev)

    add_devices(devs, True)
    return True


class LutronCasetaLight(LutronCasetaDevice, SwitchDevice):
    """Representation of a Lutron Caseta switch."""

    def __init__(self, device, bridge):
        """Initialize the switch."""
        LutronCasetaDevice.__init__(self, device, bridge)

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._smartbridge.turn_on(self._device_id)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._smartbridge.turn_off(self._device_id)

    @property
    def is_on(self):
        """Return true if device is on."""
        _LOGGER.debug(self._state)
        return self._state["current_state"] > 0

    def update(self):
        """Called when forcing a refresh of the device."""
        self._state = self._smartbridge.get_device_by_id(self._device_id)

    @property
    def should_poll(self):
        """No polling needed."""
        return False
