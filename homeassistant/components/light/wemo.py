"""
Support for Belkin WeMo lights.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.wemo/
"""
import asyncio
import logging
from datetime import timedelta

import homeassistant.util as util
import homeassistant.util.color as color_util
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_RGB_COLOR, ATTR_TRANSITION,
    ATTR_XY_COLOR, SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_RGB_COLOR,
    SUPPORT_TRANSITION, SUPPORT_XY_COLOR)
from homeassistant.loader import get_component

DEPENDENCIES = ['wemo']

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

_LOGGER = logging.getLogger(__name__)

SUPPORT_WEMO = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_RGB_COLOR |
                SUPPORT_TRANSITION | SUPPORT_XY_COLOR)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up discovered WeMo switches."""
    import pywemo.discovery as discovery

    if discovery_info is not None:
        location = discovery_info['ssdp_description']
        mac = discovery_info['mac_address']
        device = discovery.device_from_description(location, mac)

        if device.model_name == 'Dimmer':
            add_devices([WemoDimmer(device)])
        else:
            setup_bridge(device, add_devices)


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
        return self.device.uniqueID

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


class WemoDimmer(Light):
    """Representation of a WeMo dimmer."""

    def __init__(self, device):
        """Initialize the WeMo dimmer."""
        self.wemo = device
        self._brightness = None
        self._state = None

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register update callback."""
        wemo = get_component('wemo')
        # The register method uses a threading condition, so call via executor.
        # and yield from to wait until the task is done.
        yield from self.hass.async_add_job(
            wemo.SUBSCRIPTION_REGISTRY.register, self.wemo)
        # The on method just appends to a defaultdict list.
        wemo.SUBSCRIPTION_REGISTRY.on(self.wemo, None, self._update_callback)

    def _update_callback(self, _device, _type, _params):
        """Update the state by the Wemo device."""
        _LOGGER.debug("Subscription update for  %s", _device)
        updated = self.wemo.subscription_update(_type, _params)
        self._update(force_update=(not updated))
        self.schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return the ID of this WeMo dimmer."""
        return self.wemo.serialnumber

    @property
    def name(self):
        """Return the name of the dimmer if any."""
        return self.wemo.name

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def should_poll(self):
        """No polling needed with subscriptions."""
        return False

    @property
    def brightness(self):
        """Return the brightness of this light between 1 and 100."""
        return self._brightness

    @property
    def is_on(self):
        """Return true if dimmer is on. Standby is on."""
        return self._state

    def _update(self, force_update=True):
        """Update the device state."""
        try:
            self._state = self.wemo.get_state(force_update)
            wemobrightness = int(self.wemo.get_brightness(force_update))
            self._brightness = int((wemobrightness * 255) / 100)
        except AttributeError as err:
            _LOGGER.warning("Could not update status for %s (%s)",
                            self.name, err)

    def turn_on(self, **kwargs):
        """Turn the dimmer on."""
        self.wemo.on()

        # Wemo dimmer switches use a range of [0, 100] to control
        # brightness. Level 255 might mean to set it to previous value
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            brightness = int((brightness / 255) * 100)
        else:
            brightness = 255
        self.wemo.set_brightness(brightness)

    def turn_off(self, **kwargs):
        """Turn the dimmer off."""
        self.wemo.off()
