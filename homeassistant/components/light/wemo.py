"""
Support for WeMo Dimmer switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.wemo/
"""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS_PCT, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light, DOMAIN)
from homeassistant.util import convert
from homeassistant.const import (
    STATE_OFF, STATE_ON,)
from homeassistant.loader import get_component

DEPENDENCIES = ['wemo']

_LOGGER = logging.getLogger(__name__)

ATTR_SENSOR_STATE = 'sensor_state'
ATTR_SWITCH_MODE = 'switch_mode'
ATTR_CURRENT_STATE_DETAIL = 'state_detail'

WEMO_ON = 1
WEMO_OFF = 0

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

    def __init__(self, device):
        """Initialize the WeMo switch."""
        self.wemo = device
        self.insight_params = None
        self.maker_params = None
        self.coffeemaker_mode = None
        self._state = None
        # look up model name once as it incurs network traffic
        self._model_name = self.wemo.model_name

        wemo = get_component('wemo')
        wemo.SUBSCRIPTION_REGISTRY.register(self.wemo)
        wemo.SUBSCRIPTION_REGISTRY.on(self.wemo, None, self._update_callback)

    def _update_callback(self, _device, _type, _params):
        """Update the state by the Wemo device."""
        _LOGGER.info("Subscription update for  %s", _device)
        updated = self.wemo.subscription_update(_type, _params)
        self._update(force_update=(not updated))

        if not hasattr(self, 'hass'):
            return
        self.schedule_update_ha_state()

        
