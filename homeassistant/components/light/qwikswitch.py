"""
Support for Qwikswitch Relays and Dimmers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.qwikswitch/
"""
import logging

import homeassistant.components.qwikswitch as qwikswitch

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['qwikswitch']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the lights from the main Qwikswitch component."""
    if discovery_info is None:
        _LOGGER.error("Configure Qwikswitch component failed")
        return False

    add_devices(qwikswitch.QSUSB['light'])
    return True
