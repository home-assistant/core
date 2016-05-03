"""
Support for Qwikswitch Relays as HA Switches.

See the main component for more info
"""
import logging
from homeassistant.components.qwikswitch import QSUSB as qsusb

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Store add_devices for the 'switch' components."""
    if qsusb is None:
        _LOGGER.error('Configure main Qwikswitch component')
        return False
    _LOGGER.info('Qwikswitch switch setup_platform called')
    qsusb.add_devices_switch = add_devices
