"""
Support for Vera switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.vera/
"""
import logging

from homeassistant.components.hdmi_cec import CecDevice, CEC_DEVICES, CEC_CLIENT
from homeassistant.components.switch import SwitchDevice, DOMAIN
from homeassistant.const import STATE_OFF, STATE_STANDBY

DEPENDENCIES = ['hdmi_cec']

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + '.{}'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return Vera switches."""
    _LOGGER.info("setting CEC switches %s", CEC_DEVICES['switch'])
    add_devices(
        CecSwitch(hass, CEC_CLIENT, device) for
        device in CEC_DEVICES['switch'])


class CecSwitch(CecDevice, SwitchDevice):
    """Representation of a Vera Switch."""

    def __init__(self, hass, cec_client, logical):
        """Initialize the Vera device."""
        _LOGGER.info("Creating %s switch %d", DOMAIN, logical)
        self._state = False
        CecDevice.__init__(self, hass, cec_client, logical)
        self.entity_id = "%s.%s_%s" % (DOMAIN, 'hdmi', hex(self._logical_address)[2:])

    @property
    def is_standby(self):
        """Return true if device is in standby."""
        return self._state == STATE_OFF or self._state == STATE_STANDBY
