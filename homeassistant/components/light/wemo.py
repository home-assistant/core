"""
Support for Belkin WeMo lights.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.wemo/
"""
import logging
from datetime import timedelta

import homeassistant.util as util
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS)

DEPENDENCIES = ['wemo']

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup WeMo bridges and register connected lights."""
    import pywemo.discovery as discovery

    if discovery_info is not None:
        location = discovery_info[2]
        mac = discovery_info[3]
        device = discovery.device_from_description(location, mac)

        if device:
            setup_bridge(device, add_devices_callback)


def setup_bridge(bridge, add_devices_callback):
    """Setup a WeMo link."""
    lights = {}

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_lights():
        """Update the WeMo led objects with latest info from the bridge."""
        bridge.bridge_get_lights()

        new_lights = []

        for light_id, info in bridge.Lights.items():
            if light_id not in lights:
                lights[light_id] = WemoLight(bridge, light_id, info,
                                             update_lights)
                new_lights.append(lights[light_id])
            else:
                lights[light_id].info = info

        if new_lights:
            add_devices_callback(new_lights)

    update_lights()


class WemoLight(Light):
    """Representation of a WeMo light."""

    def __init__(self, bridge, light_id, info, update_lights):
        """Initialize the light."""
        self.bridge = bridge
        self.light_id = light_id
        self.info = info
        self.update_lights = update_lights

    @property
    def unique_id(self):
        """Return the ID of this light."""
        deviceid = self.bridge.light_get_id(self.info)
        return "{}.{}".format(self.__class__, deviceid)

    @property
    def name(self):
        """Return the name of the light."""
        return self.bridge.light_name(self.info)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        state = self.bridge.light_get_state(self.info)
        return int(state['dim'])

    @property
    def is_on(self):
        """True if device is on."""
        state = self.bridge.light_get_state(self.info)
        return int(state['state'])

    def turn_on(self, **kwargs):
        """Turn the light on."""
        dim = kwargs.get(ATTR_BRIGHTNESS, self.brightness)
        self.bridge.light_set_state(self.info, state=1, dim=dim)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self.bridge.light_set_state(self.info, state=0, dim=0)

    def update(self):
        """Synchronize state with bridge."""
        self.update_lights(no_throttle=True)
