"""
Support for Qwikswitch Relays as HA Switches.

See the main component for more info
"""
import logging
import homeassistant.components.qwikswitch as qwikswitch
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['qwikswitch']


class QSSwitch(qwikswitch.QSToggleEntity, SwitchDevice):
    """Switch based on a Qwikswitch relay module."""

    pass


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Store add_devices for the 'switch' components."""
    if discovery_info is None or 'qsusb_id' not in discovery_info:
        logging.getLogger(__name__).error(
            'Configure main Qwikswitch component')
        return False

    qsusb = qwikswitch.QSUSB[discovery_info['qsusb_id']]

    for item in qsusb.ha_devices:
        if item['type'] == 'switch':
            dev = QSSwitch(item, qsusb)
            add_devices([dev])
            qsusb.ha_objects[item['id']] = dev
