"""
Support for WeMo Dimmer switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.wemo/
"""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS_PCT, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, SUPPORT_TRANSITION, Light, DOMAIN)
from homeassistant.util import convert
from homeassistant.const import (
    STATE_OFF, STATE_ON,)
from homeassistant.loader import get_component

DEPENDENCIES = ['wemo']

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

_LOGGER = logging.getLogger(__name__)

SUPPORT_WEMO = (SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION)

ATTR_SENSOR_STATE = 'sensor_state'
ATTR_SWITCH_MODE = 'switch_mode'
ATTR_CURRENT_STATE_DETAIL = 'state_detail'

WEMO_ON = 1
WEMO_OFF = 0
WEMO_STANDBY = 8

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
        """Initialize the WeMo dimmer."""
        self.wemo = device
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

        # Used for value change event handling
        self.value_added()
        self.update_properties()

    @property
    def should_poll(self):
        """No polling needed with subscriptions."""
        if self._model_name == 'Insight':
            return True
        return False

    @property
    def unique_id(self):
        """Return the ID of this WeMo dimmer."""
        return "{}.{}".format(self.__class__, self.wemo.serialnumber)

    @property
    def name(self):
        """Return the name of the dimmer if any."""
        return self.wemo.name

    @property
    def is_on(self):
        """Return true if dimmer is on. Standby is on."""
        return self._state
        
    def turn_on(self, **kwargs):
        """Turn the dimmer on."""
        self._state = WEMO_ON
        self.wemo.on()
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the dimmer off."""
        self._state = WEMO_OFF
        self.wemo.off()
        self.schedule_update_ha_state()
