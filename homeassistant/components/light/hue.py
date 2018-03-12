"""
This component provides light support for the Philips Hue system.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.hue/
"""
import asyncio
from datetime import timedelta
import logging
import random

import async_timeout

import homeassistant.components.hue as hue
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_EFFECT, ATTR_FLASH, ATTR_RGB_COLOR,
    ATTR_TRANSITION, ATTR_XY_COLOR, EFFECT_COLORLOOP, EFFECT_RANDOM,
    FLASH_LONG, FLASH_SHORT, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP, SUPPORT_EFFECT, SUPPORT_FLASH, SUPPORT_RGB_COLOR,
    SUPPORT_TRANSITION, SUPPORT_XY_COLOR, Light)
import homeassistant.util as util
import homeassistant.util.color as color_util

DEPENDENCIES = ['hue']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

SUPPORT_HUE_ON_OFF = (SUPPORT_FLASH | SUPPORT_TRANSITION)
SUPPORT_HUE_DIMMABLE = (SUPPORT_HUE_ON_OFF | SUPPORT_BRIGHTNESS)
SUPPORT_HUE_COLOR_TEMP = (SUPPORT_HUE_DIMMABLE | SUPPORT_COLOR_TEMP)
SUPPORT_HUE_COLOR = (SUPPORT_HUE_DIMMABLE | SUPPORT_EFFECT |
                     SUPPORT_RGB_COLOR | SUPPORT_XY_COLOR)
SUPPORT_HUE_EXTENDED = (SUPPORT_HUE_COLOR_TEMP | SUPPORT_HUE_COLOR)

SUPPORT_HUE = {
    'Extended color light': SUPPORT_HUE_EXTENDED,
    'Color light': SUPPORT_HUE_COLOR,
    'Dimmable light': SUPPORT_HUE_DIMMABLE,
    'On/Off plug-in unit': SUPPORT_HUE_ON_OFF,
    'Color temperature light': SUPPORT_HUE_COLOR_TEMP
    }

ATTR_IS_HUE_GROUP = 'is_hue_group'


class BoolProxy:
    """Proxy value for a boolean."""

    def __init__(self, initial):
        """Initialize boolean proxy."""
        self.value = initial

    def __bool__(self):
        """Return the proxied boolean value."""
        return self.value


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the Hue lights."""
    if discovery_info is None:
        return

    bridge = hass.data[hue.DOMAIN][discovery_info['bridge_id']]
    aiobridge = bridge.aiobridge
    cur_lights = {}
    cur_groups = {}
    bridge_available = BoolProxy(True)
    await async_update_lights(
        hass, aiobridge, cur_lights, cur_groups, async_add_devices,
        bridge_available, bridge.allow_groups, bridge.allow_unreachable)


async def async_update_lights(hass, bridge, cur_lights, cur_groups,
                              async_add_devices, bridge_available,
                              allow_groups, allow_unreachable):
    """Update the lights."""
    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    async def throttled_update(**kw):
        """Throttled update lights."""
        bridge_available.value = True
        try:
            with async_timeout.timeout(9):
                await async_update_lights(
                    hass, bridge, cur_lights, cur_groups, async_add_devices,
                    bridge_available, allow_groups, allow_unreachable, **kw)
        except asyncio.TimeoutError:
            _LOGGER.error('Unable to reach bridge')

            bridge_available.value = False

            for light in cur_lights.values():
                light.async_schedule_update_ha_state()

            for group in cur_groups.values():
                group.async_schedule_update_ha_state()

    await bridge.lights.update()

    new_lights = []
    for light_id in bridge.lights:
        if light_id in cur_lights:
            cur_lights[light_id].async_schedule_update_ha_state()
        else:
            cur_lights[light_id] = HueLight(
                bridge.lights[light_id], throttled_update, bridge_available,
                allow_unreachable)

            new_lights.append(cur_lights[light_id])

    if not allow_groups:
        if new_lights:
            async_add_devices(new_lights)
        return

    await bridge.groups.update()

    for group_id in bridge.groups:
        if group_id in cur_groups:
            cur_groups[group_id].async_schedule_update_ha_state()
        else:
            cur_groups[group_id] = HueLight(
                bridge.groups[group_id], throttled_update, bridge_available,
                allow_unreachable, True)

            new_lights.append(cur_groups[group_id])

    if new_lights:
        async_add_devices(new_lights)


class HueLight(Light):
    """Representation of a Hue light."""

    def __init__(self, light, update_lights_cb, bridge_available,
                 allow_unreachable, is_group=False):
        """Initialize the light."""
        self.light = light
        self.async_update_lights = update_lights_cb
        self.bridge_available = bridge_available
        self.allow_unreachable = allow_unreachable
        self.is_group = is_group

        if is_group:
            self.is_osram = False
            self.is_philips = False
        else:
            self.is_osram = light.manufacturername == 'OSRAM'
            self.is_philips = light.manufacturername == 'Philips'

    @property
    def unique_id(self):
        """Return the ID of this Hue light."""
        if self.is_group:
            return None
        return self.light.unique_id

    @property
    def name(self):
        """Return the name of the Hue light."""
        return self.light.name

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        if self.is_group:
            return self.light.action.get('bri')
        return self.light.state.get('bri')

    @property
    def xy_color(self):
        """Return the XY color value."""
        if self.is_group:
            return self.light.action.get('xy')
        return self.light.state.get('xy')

    @property
    def color_temp(self):
        """Return the CT color value."""
        if self.is_group:
            return self.light.action.get('ct')
        return self.light.state.get('ct')

    @property
    def is_on(self):
        """Return true if device is on."""
        if self.is_group:
            return self.light.state['any_on']
        return self.light.state['on']

    @property
    def available(self):
        """Return if light is available."""
        return self.bridge_available and (self.is_group or
                                          self.allow_unreachable or
                                          self.light.state['reachable'])

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_HUE.get(self.light.type, SUPPORT_HUE_EXTENDED)

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return [EFFECT_COLORLOOP, EFFECT_RANDOM]

    async def async_turn_on(self, **kwargs):
        """Turn the specified or all lights on."""
        command = {'on': True}

        if ATTR_TRANSITION in kwargs:
            command['transitiontime'] = int(kwargs[ATTR_TRANSITION] * 10)

        if ATTR_XY_COLOR in kwargs:
            if self.is_osram:
                color_hue, sat = color_util.color_xy_to_hs(
                    *kwargs[ATTR_XY_COLOR])
                command['hue'] = color_hue / 360 * 65535
                command['sat'] = sat / 100 * 255
            else:
                command['xy'] = kwargs[ATTR_XY_COLOR]
        elif ATTR_RGB_COLOR in kwargs:
            if self.is_osram:
                hsv = color_util.color_RGB_to_hsv(
                    *(int(val) for val in kwargs[ATTR_RGB_COLOR]))
                command['hue'] = hsv[0] / 360 * 65535
                command['sat'] = hsv[1] / 100 * 255
                command['bri'] = hsv[2] / 100 * 255
            else:
                xyb = color_util.color_RGB_to_xy(
                    *(int(val) for val in kwargs[ATTR_RGB_COLOR]))
                command['xy'] = xyb[0], xyb[1]
        elif ATTR_COLOR_TEMP in kwargs:
            temp = kwargs[ATTR_COLOR_TEMP]
            command['ct'] = max(self.min_mireds, min(temp, self.max_mireds))

        if ATTR_BRIGHTNESS in kwargs:
            command['bri'] = kwargs[ATTR_BRIGHTNESS]

        flash = kwargs.get(ATTR_FLASH)

        if flash == FLASH_LONG:
            command['alert'] = 'lselect'
            del command['on']
        elif flash == FLASH_SHORT:
            command['alert'] = 'select'
            del command['on']
        else:
            command['alert'] = 'none'

        effect = kwargs.get(ATTR_EFFECT)

        if effect == EFFECT_COLORLOOP:
            command['effect'] = 'colorloop'
        elif effect == EFFECT_RANDOM:
            command['hue'] = random.randrange(0, 65535)
            command['sat'] = random.randrange(150, 254)
        elif self.is_philips:
            command['effect'] = 'none'

        if self.is_group:
            await self.light.set_action(**command)
        else:
            await self.light.set_state(**command)

    async def async_turn_off(self, **kwargs):
        """Turn the specified or all lights off."""
        command = {'on': False}

        if ATTR_TRANSITION in kwargs:
            command['transitiontime'] = int(kwargs[ATTR_TRANSITION] * 10)

        flash = kwargs.get(ATTR_FLASH)

        if flash == FLASH_LONG:
            command['alert'] = 'lselect'
            del command['on']
        elif flash == FLASH_SHORT:
            command['alert'] = 'select'
            del command['on']
        else:
            command['alert'] = 'none'

        if self.is_group:
            await self.light.set_action(**command)
        else:
            await self.light.set_state(**command)

    async def async_update(self):
        """Synchronize state with bridge."""
        await self.async_update_lights(no_throttle=True)

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = {}
        if self.is_group:
            attributes[ATTR_IS_HUE_GROUP] = self.is_group
        return attributes
