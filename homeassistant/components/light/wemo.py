"""
Support for Belkin WeMo Dimmers / Lights.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.wemo/
"""

##THIS IS NON-Functional. Only discovers the light at this time, cannot control it!
import logging
from datetime import timedelta

import homeassistant.util as util
import homeassistant.util.color as color_util
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_RGB_COLOR, ATTR_TRANSITION,
    ATTR_XY_COLOR, SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_RGB_COLOR,
    SUPPORT_TRANSITION, SUPPORT_XY_COLOR)
from homeassistant.const import (
    STATE_OFF, STATE_ON, STATE_STANDBY, STATE_UNKNOWN)

DEPENDENCIES = ['wemo']

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

_LOGGER = logging.getLogger(__name__)

SUPPORT_WEMO = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_RGB_COLOR |
                SUPPORT_TRANSITION | SUPPORT_XY_COLOR)

WEMO_ON = 1
WEMO_OFF = 0
WEMO_STANDBY = 8

# pylint: disable=unused-argument, too-many-function-args
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up discovered WeMo switches."""
    import pywemo.discovery as discovery

    if discovery_info is not None:
        location = discovery_info['ssdp_description']
        mac = discovery_info['mac_address']
        device = discovery.device_from_description(location, mac)

        if device:
            add_devices_callback([WemoDimmer(device)])

class WemoDimmer(Light):
    """Representation of a WeMo dimmer"""

    def __init__(self, device):
        """Initialize the WeMo dimmer."""
        self.wemo = device
        self._brightness = None
        self._state = None
        # look up model name once as it incurs network traffic
        self._model_name = self.wemo.model_name

    @property
    def unique_id(self):
        """Return the ID of this WeMo dimmer."""
        return "{}.{}".format(self.__class__, self.wemo.serialnumber)

    @property
    def name(self):
        """Return the name of the dimmer if any."""
        return self.wemo.name

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_WEMO

    @property
    def brightness(self):
        """Return the brightness of this light between 1 and 100"""
        brightness = self.get_brighness
        return brightness

    @property
    def is_on(self):
        """Return true if dimmer is on. Standby is on."""
        return self._state
        
    def turn_on(self, **kwargs):
        """Turn the dimmer on."""
        self._state = WEMO_ON
        transitiontime = int(kwargs.get(ATTR_TRANSITION, 0))
        
        # Wemo dimmer switches use a range of [0, 99] to control
        # brightness. Level 255 might mean to set it to previous value
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            brightness = int((self._brightness / 255) * 99)
        else:
            brightness = 255

    def turn_off(self, **kwargs):
        """Turn the dimmer off."""
        self._state = WEMO_OFF
        self.wemo.off()
        self.schedule_update_ha_state()
