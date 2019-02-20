"""Support for Belkin WeMo lights."""
import asyncio
import logging
from datetime import timedelta

import requests
import async_timeout

from homeassistant import util
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_HS_COLOR, ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_COLOR, SUPPORT_TRANSITION)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.util.color as color_util

DEPENDENCIES = ['wemo']

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

_LOGGER = logging.getLogger(__name__)

SUPPORT_WEMO = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_COLOR |
                SUPPORT_TRANSITION)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up discovered WeMo switches."""
    from pywemo import discovery

    if discovery_info is not None:
        location = discovery_info['ssdp_description']
        mac = discovery_info['mac_address']

        try:
            device = discovery.device_from_description(location, mac)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as err:
            _LOGGER.error('Unable to access %s (%s)', location, err)
            raise PlatformNotReady

        if device.model_name == 'Dimmer':
            add_entities([WemoDimmer(device)])
        else:
            setup_bridge(device, add_entities)


def setup_bridge(bridge, add_entities):
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
            add_entities(new_lights)

    update_lights()


class WemoLight(Light):
    """Representation of a WeMo light."""

    def __init__(self, device, update_lights):
        """Initialize the WeMo light."""
        self.wemo = device
        self._state = None
        self._update_lights = update_lights
        self._available = True
        self._update_lock = None
        self._brightness = None
        self._hs_color = None
        self._color_temp = None
        self._is_on = None
        self._name = self.wemo.name
        self._unique_id = self.wemo.uniqueID

    async def async_added_to_hass(self):
        """Wemo light added to HASS."""
        # Define inside async context so we know our event loop
        self._update_lock = asyncio.Lock()

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the hs color values of this light."""
        return self._hs_color

    @property
    def color_temp(self):
        """Return the color temperature of this light in mireds."""
        return self._color_temp

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._is_on

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_WEMO

    @property
    def available(self):
        """Return if light is available."""
        return self._available

    def turn_on(self, **kwargs):
        """Turn the light on."""
        transitiontime = int(kwargs.get(ATTR_TRANSITION, 0))

        hs_color = kwargs.get(ATTR_HS_COLOR)

        if hs_color is not None:
            xy_color = color_util.color_hs_to_xy(*hs_color)
            self.wemo.set_color(xy_color, transition=transitiontime)

        if ATTR_COLOR_TEMP in kwargs:
            colortemp = kwargs[ATTR_COLOR_TEMP]
            self.wemo.set_temperature(mireds=colortemp,
                                      transition=transitiontime)

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness or 255)
            self.wemo.turn_on(level=brightness, transition=transitiontime)
        else:
            self.wemo.turn_on(transition=transitiontime)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        transitiontime = int(kwargs.get(ATTR_TRANSITION, 0))
        self.wemo.turn_off(transition=transitiontime)

    def _update(self, force_update=True):
        """Synchronize state with bridge."""
        self._update_lights(no_throttle=force_update)
        self._state = self.wemo.state

        self._is_on = self._state.get('onoff') != 0
        self._brightness = self._state.get('level', 255)
        self._color_temp = self._state.get('temperature_mireds')
        self._available = True

        xy_color = self._state.get('color_xy')

        if xy_color:
            self._hs_color = color_util.color_xy_to_hs(*xy_color)
        else:
            self._hs_color = None

    async def async_update(self):
        """Synchronize state with bridge."""
        # If an update is in progress, we don't do anything
        if self._update_lock.locked():
            return

        try:
            with async_timeout.timeout(5):
                await asyncio.shield(self._async_locked_update(True))
        except asyncio.TimeoutError:
            _LOGGER.warning('Lost connection to %s', self.name)
            self._available = False

    async def _async_locked_update(self, force_update):
        """Try updating within an async lock."""
        async with self._update_lock:
            await self.hass.async_add_executor_job(self._update, force_update)


class WemoDimmer(Light):
    """Representation of a WeMo dimmer."""

    def __init__(self, device):
        """Initialize the WeMo dimmer."""
        self.wemo = device
        self._state = None
        self._available = True
        self._update_lock = None
        self._brightness = None
        self._model_name = self.wemo.model_name
        self._name = self.wemo.name
        self._serialnumber = self.wemo.serialnumber

    def _subscription_callback(self, _device, _type, _params):
        """Update the state by the Wemo device."""
        _LOGGER.debug("Subscription update for %s", self.name)
        updated = self.wemo.subscription_update(_type, _params)
        self.hass.add_job(
            self._async_locked_subscription_callback(not updated))

    async def _async_locked_subscription_callback(self, force_update):
        """Handle an update from a subscription."""
        # If an update is in progress, we don't do anything
        if self._update_lock.locked():
            return

        await self._async_locked_update(force_update)
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Wemo dimmer added to HASS."""
        # Define inside async context so we know our event loop
        self._update_lock = asyncio.Lock()

        registry = self.hass.components.wemo.SUBSCRIPTION_REGISTRY
        await self.hass.async_add_executor_job(registry.register, self.wemo)
        registry.on(self.wemo, None, self._subscription_callback)

    async def async_update(self):
        """Update WeMo state.

        Wemo has an aggressive retry logic that sometimes can take over a
        minute to return. If we don't get a state after 5 seconds, assume the
        Wemo dimmer is unreachable. If update goes through, it will be made
        available again.
        """
        # If an update is in progress, we don't do anything
        if self._update_lock.locked():
            return

        try:
            with async_timeout.timeout(5):
                await asyncio.shield(self._async_locked_update(True))
        except asyncio.TimeoutError:
            _LOGGER.warning('Lost connection to %s', self.name)
            self._available = False
            self.wemo.reconnect_with_device()

    async def _async_locked_update(self, force_update):
        """Try updating within an async lock."""
        async with self._update_lock:
            await self.hass.async_add_executor_job(self._update, force_update)

    @property
    def unique_id(self):
        """Return the ID of this WeMo dimmer."""
        return self._serialnumber

    @property
    def name(self):
        """Return the name of the dimmer if any."""
        return self._name

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

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

            if not self._available:
                _LOGGER.info('Reconnected to %s', self.name)
                self._available = True
        except AttributeError as err:
            _LOGGER.warning("Could not update status for %s (%s)",
                            self.name, err)
            self._available = False

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

    @property
    def available(self):
        """Return if dimmer is available."""
        return self._available
