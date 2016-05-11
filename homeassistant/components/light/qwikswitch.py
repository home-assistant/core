"""
Support for Qwikswitch Relays and Dimmers as HA Lights.

See the main component for more info
"""
import logging
from homeassistant.components.qwikswitch import QSToggleEntity, QSUSB
from homeassistant.components.light import Light

DEPENDENCIES = ['qwikswitch']


class QSLight(QSToggleEntity, Light):
    """Light based on a Qwikswitch relay/dimmer module."""

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Store add_devices for the 'light' components."""
    if discovery_info is None or 'qsusb_id' not in discovery_info:
        _LOGGER.error('Configure main Qwikswitch component')
        return False

    _LOGGER.info('Qwikswitch light setup_platform called')
    qsusb = QSUSB[discovery_info['qsusb_id']]

    for item in qsusb.ha_devices:
        if item['id'] in qsusb.ha_objects or \
           item['type'] not in ['dim', 'rel']:
            continue
        if item['type'] == 'rel' and item['name'].lower().endswith(' switch'):
            continue
        dev = QSLight(item, qsusb)
        add_devices([dev])
        qsusb.ha_objects[item['id']] = dev
