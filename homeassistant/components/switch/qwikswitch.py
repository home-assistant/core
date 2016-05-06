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
    from homeassistant.components.qwikswitch import ADD_DEVICES

    if ADD_DEVICES is None:
        _LOGGER.error('Configure main Qwikswitch component')
        return False

    _LOGGER.info('Qwikswitch switch setup_platform called')
    ADD_DEVICES['switch'] = add_devices
