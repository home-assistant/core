"""
Support for Qwikswitch relays.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.qwikswitch/
"""
import logging
import homeassistant.components.qwikswitch as qwikswitch

DEPENDENCIES = ['qwikswitch']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Add switched from the main Qwikswitch component."""
    if discovery_info is None:
        logging.getLogger(__name__).error(
            'Configure main Qwikswitch component')
        return False

    add_devices(qwikswitch.QSUSB['switch'])
    return True
