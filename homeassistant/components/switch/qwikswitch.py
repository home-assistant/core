"""
Support for Qwikswitch Relays as HA Switches.

See the main component for more info
"""
import logging
from homeassistant.components.qwikswitch import QSToggleEntity
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['qwikswitch']


class QSSwitch(QSToggleEntity, SwitchDevice):
    """Switch based on a Qwikswitch relay module."""


_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Store add_devices for the 'switch' components."""
    if discovery_info is None or 'qsusb' not in discovery_info:
        _LOGGER.error('Configure main Qwikswitch component')
        return False

    _LOGGER.info('Qwikswitch light setup_platform called')
    qsusb = discovery_info['qsusb']

    for item in qsusb.ha_devices:
        if item['type'] == 'rel' and \
           item['name'].lower().endswith(' switch'):
            # Remove the ' Switch' name postfix for HA
            item['name'] = item['name'][:-7]
            dev = QSSwitch(item, qsusb)
            add_devices([dev])
            qsusb.ha_objects[item['id']] = dev
