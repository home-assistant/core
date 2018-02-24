"""
Support for Qwikswitch Relays and Dimmers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.qwikswitch/
"""
import logging

DEPENDENCIES = ['qwikswitch']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Add lights from the main Qwikswitch component."""
    if discovery_info is None:
        logging.getLogger(__name__).error(
            "Configure Qwikswitch Light component failed")
        return False

    add_devices(hass.data['qwikswitch']['light'])
    return True
