"""
Support for HDMI CEC devices as switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hdmi_cec/
"""
import logging

from homeassistant.components.hdmi_cec import CecDevice, CEC_CLIENT, ATTR_NEW
from homeassistant.components.switch import SwitchDevice, DOMAIN
from homeassistant.const import STATE_OFF, STATE_STANDBY

DEPENDENCIES = ['hdmi_cec']

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + '.{}'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return HDMI devices as switches."""
    if ATTR_NEW in discovery_info:
        _LOGGER.info("Setting up devices %s", discovery_info[ATTR_NEW])
        add_devices(CecSwitch(hass, CEC_CLIENT, device) for device in discovery_info[ATTR_NEW])


class CecSwitch(CecDevice, SwitchDevice):
    """Representation of a HDMI device as a Switch."""

    def __init__(self, hass, cec_client, logical):
        """Initialize the HDMI device."""
        _LOGGER.info("Creating %s switch %d", DOMAIN, logical)
        self._state = False
        CecDevice.__init__(self, hass, cec_client, logical)
        self.entity_id = "%s.%s_%s" % (DOMAIN, 'hdmi', hex(self._logical_address)[2:])

    @property
    def is_standby(self):
        """Return true if device is in standby."""
        return self._state == STATE_OFF or self._state == STATE_STANDBY
