"""
Support for Qwikswitch relays.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.qwikswitch/
"""
import logging

DEPENDENCIES = ['qwikswitch']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Add switches from the main Qwikswitch component."""
    if discovery_info is None:
        logging.getLogger(__name__).error(
            "Configure Qwikswitch Switch component failed")
        return False

    add_devices(hass.data['qwikswitch']['switch'])
    return True
