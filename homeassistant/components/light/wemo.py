"""
Support for WeMo Dimmer switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.wemo/
"""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS_PCT, SUPPORT_BRIGHTNESS, Light, DOMAIN)
DEPENDENCIES = ['wemo']

_LOGGER = logging.getLogger(__name__)

ATTR_SENSOR_STATE = 'sensor_state'
ATTR_SWITCH_MODE = 'switch_mode'
ATTR_CURRENT_STATE_DETAIL = 'state_detail'
ATTR_COFFEMAKER_MODE = 'coffeemaker_mode'

MAKER_SWITCH_MOMENTARY = 'momentary'
MAKER_SWITCH_TOGGLE = 'toggle'

WEMO_ON = 1
WEMO_OFF = 0

# pylint: disable=unused-argument, too-many-function-args
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up discovered WeMo dimmers."""
    import pywemo.discovery as discovery

    if discovery_info is not None:
        location = discovery_info['ssdp_description']
        mac = discovery_info['mac_address']
        device = discovery.device_from_description(location, mac)

        if device:
            add_devices_callback([WemoDimmer(device)])

class WemoDimmer(light)
    ""Representation of a WeMo dimmer""


        