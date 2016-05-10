"""
Support for Qwikswitch Relays as HA Switches.

See the main component for more info
"""
import logging

DEPENDENCIES = ['qwikswitch']

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Store add_devices for the 'switch' components."""
    if discovery_info is None or 'add_devices' not in discovery_info:
        _LOGGER.error('Configure main Qwikswitch component')
        return False

    _LOGGER.info('Qwikswitch switch setup_platform called')
    discovery_info['add_devices']['switch'] = add_devices
