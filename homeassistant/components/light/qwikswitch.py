"""
Support for Qwikswitch Relays and Dimmers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.qwikswitch/
"""
import logging
import homeassistant.components.qwikswitch as qwikswitch
from homeassistant.components.light import Light

DEPENDENCIES = ['qwikswitch']


class QSLight(qwikswitch.QSToggleEntity, Light):
    """Light based on a Qwikswitch relay/dimmer module."""

    pass


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Store add_devices for the light components."""
    if discovery_info is None or 'qsusb_id' not in discovery_info:
        logging.getLogger(__name__).error(
            'Configure main Qwikswitch component')
        return False

    qsusb = qwikswitch.QSUSB[discovery_info['qsusb_id']]

    for item in qsusb.ha_devices:
        if item['type'] not in ['dim', 'rel']:
            continue
        dev = QSLight(item, qsusb)
        add_devices([dev])
        qsusb.ha_objects[item['id']] = dev
