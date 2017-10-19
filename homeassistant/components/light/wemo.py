"""
Support for Belkin WeMo lights and dimmer.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.wemo/
"""
import logging
from datetime import timedelta

import homeassistant.util as util
import homeassistant.util.color as color_util
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_RGB_COLOR, ATTR_TRANSITION,
    ATTR_XY_COLOR, SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_RGB_COLOR,
    SUPPORT_TRANSITION, ATTR_BRIGHTNESS_PCT, VALID_BRIGHTNESS, VALID_BRIGHTNESS_PCT, 
    SUPPORT_XY_COLOR)
from homeassistant.const import (
    STATE_OFF, STATE_ON, STATE_STANDBY, STATE_UNKNOWN)
from homeassistant.loader import get_component

DEPENDENCIES = ['wemo']

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)
ATTR_SWITCH_MODE = 'switch_mode'
WEMO_ON = 1
WEMO_OFF = 0
WEMO_STANDBY = 8

_LOGGER = logging.getLogger(__name__)

SUPPORT_WEMO = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_RGB_COLOR |
                SUPPORT_TRANSITION | SUPPORT_XY_COLOR)


def setup_platform(hass, config, add_devices, add_devices_callback, discovery_info=None):
    """Set up the WeMo bridges and register connected lights."""
    import pywemo.discovery as discovery

    if discovery_info is not None:
        location = discovery_info['ssdp_description']
        mac = discovery_info['mac_address']
        device = discovery.device_from_description(location, mac)

        if device:
            setup_bridge(device, add_devices)
            
        if device:
            add_devices_callback([WemoDimmer(device)])


def setup_bridge(bridge, add_devices):
    """Set up a WeMo link."""
    lights = {}

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_lights():
        """Update the WeMo led objects with latest info from the bridge."""
        bridge.bridge_update()

        new_lights = []

        for light_id, device in bridge.Lights.items():
            if light_id not in lights:
                lights[light_id] = WemoLight(device, update_lights)
                new_lights.append(lights[light_id])

        if new_lights:
            add_devices(new_lights)

    update_lights()


class WemoLight(Light):
    """Representation of a WeMo light."""

    def __init__(self, device, update_lights):
        """Initialize the WeMo light."""
        self.light_id = device.name
        self.device = device
        self.update_lights = update_lights

    @property
    def unique_id(self):
        """Return the ID of this light."""
        deviceid = self.device.uniqueID
        return '{}.{}'.format(self.__class__, deviceid)

    @property
    def name(self):
        """Return the name of the light."""
        return self.device.name

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self.device.state.get('level', 255)

    @property
    def xy_color(self):
        """Return the XY color values of this light."""
        return self.device.state.get('color_xy')

    @property
    def color_temp(self):
        """Return the color temperature of this light in mireds."""
        return self.device.state.get('temperature_mireds')

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.device.state['onoff'] != 0

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_WEMO

    def turn_on(self, **kwargs):
        """Turn the light on."""
        transitiontime = int(kwargs.get(ATTR_TRANSITION, 0))

        if ATTR_XY_COLOR in kwargs:
            xycolor = kwargs[ATTR_XY_COLOR]
        elif ATTR_RGB_COLOR in kwargs:
            xycolor = color_util.color_RGB_to_xy(
                *(int(val) for val in kwargs[ATTR_RGB_COLOR]))
            kwargs.setdefault(ATTR_BRIGHTNESS, xycolor[2])
        else:
            xycolor = None

        if xycolor is not None:
            self.device.set_color(xycolor, transition=transitiontime)

        if ATTR_COLOR_TEMP in kwargs:
            colortemp = kwargs[ATTR_COLOR_TEMP]
            self.device.set_temperature(mireds=colortemp,
                                        transition=transitiontime)

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness or 255)
            self.device.turn_on(level=brightness, transition=transitiontime)
        else:
            self.device.turn_on(transition=transitiontime)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        transitiontime = int(kwargs.get(ATTR_TRANSITION, 0))
        self.device.turn_off(transition=transitiontime)

    def update(self):
        """Synchronize state with bridge."""
        self.update_lights(no_throttle=True)


class WemoDimmer(light)
    ""Representation of a WeMo dimmer""

    def __init__(self, device):
        """Initialize the WeMo dimmer."""
        self.wemo = device
        self._brightness = None
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
        return (SUPPORT_BRIGHTNESS_PCT | SUPPORT_TRANSITION | SUPPORT_EFFECT)

    @property
    def brightness(self):
        """Return the brightness of this light between 1 and 100"""
        brightness = self._brighness
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

