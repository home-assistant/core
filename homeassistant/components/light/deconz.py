"""
Support for deCONZ light.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.deconz/
"""
from homeassistant.components.deconz import (
    DOMAIN as DATA_DECONZ, DATA_DECONZ_ID, DATA_DECONZ_UNSUB)
from homeassistant.components.deconz.const import CONF_ALLOW_DECONZ_GROUPS
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_EFFECT, ATTR_FLASH, ATTR_HS_COLOR,
    ATTR_TRANSITION, EFFECT_COLORLOOP, FLASH_LONG, FLASH_SHORT,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR, SUPPORT_COLOR_TEMP, SUPPORT_EFFECT,
    SUPPORT_FLASH, SUPPORT_TRANSITION, Light)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.util.color as color_util

DEPENDENCIES = ['deconz']


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Old way of setting up deCONZ lights and group."""
    pass


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the deCONZ lights and groups from a config entry."""
    @callback
    def async_add_light(lights):
        """Add light from deCONZ."""
        entities = []
        for light in lights:
            entities.append(DeconzLight(light))
        async_add_devices(entities, True)

    hass.data[DATA_DECONZ_UNSUB].append(
        async_dispatcher_connect(hass, 'deconz_new_light', async_add_light))

    @callback
    def async_add_group(groups):
        """Add group from deCONZ."""
        entities = []
        allow_group = config_entry.data.get(CONF_ALLOW_DECONZ_GROUPS, True)
        for group in groups:
            if group.lights and allow_group:
                entities.append(DeconzLight(group))
        async_add_devices(entities, True)

    hass.data[DATA_DECONZ_UNSUB].append(
        async_dispatcher_connect(hass, 'deconz_new_group', async_add_group))

    async_add_light(hass.data[DATA_DECONZ].lights.values())
    async_add_group(hass.data[DATA_DECONZ].groups.values())


class DeconzLight(Light):
    """Representation of a deCONZ light."""

    def __init__(self, light):
        """Set up light and add update callback to get data from websocket."""
        self._light = light

        self._features = SUPPORT_BRIGHTNESS
        self._features |= SUPPORT_FLASH
        self._features |= SUPPORT_TRANSITION

        if self._light.ct is not None:
            self._features |= SUPPORT_COLOR_TEMP

        if self._light.xy is not None:
            self._features |= SUPPORT_COLOR

        if self._light.effect is not None:
            self._features |= SUPPORT_EFFECT

    async def async_added_to_hass(self):
        """Subscribe to lights events."""
        self._light.register_async_callback(self.async_update_callback)
        self.hass.data[DATA_DECONZ_ID][self.entity_id] = self._light.deconz_id

    @callback
    def async_update_callback(self, reason):
        """Update the light's state."""
        self.async_schedule_update_ha_state()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._light.brightness

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return [EFFECT_COLORLOOP]

    @property
    def color_temp(self):
        """Return the CT color value."""
        return self._light.ct

    @property
    def hs_color(self):
        """Return the hs color value."""
        if self._light.colormode in ('xy', 'hs') and self._light.xy:
            return color_util.color_xy_to_hs(*self._light.xy)
        return None

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._light.state

    @property
    def name(self):
        """Return the name of the light."""
        return self._light.name

    @property
    def unique_id(self):
        """Return a unique identifier for this light."""
        return self._light.uniqueid

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._features

    @property
    def available(self):
        """Return True if light is available."""
        return self._light.reachable

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    async def async_turn_on(self, **kwargs):
        """Turn on light."""
        data = {'on': True}

        if ATTR_COLOR_TEMP in kwargs:
            data['ct'] = kwargs[ATTR_COLOR_TEMP]

        if ATTR_HS_COLOR in kwargs:
            data['xy'] = color_util.color_hs_to_xy(*kwargs[ATTR_HS_COLOR])

        if ATTR_BRIGHTNESS in kwargs:
            data['bri'] = kwargs[ATTR_BRIGHTNESS]

        if ATTR_TRANSITION in kwargs:
            data['transitiontime'] = int(kwargs[ATTR_TRANSITION]) * 10

        if ATTR_FLASH in kwargs:
            if kwargs[ATTR_FLASH] == FLASH_SHORT:
                data['alert'] = 'select'
                del data['on']
            elif kwargs[ATTR_FLASH] == FLASH_LONG:
                data['alert'] = 'lselect'
                del data['on']

        if ATTR_EFFECT in kwargs:
            if kwargs[ATTR_EFFECT] == EFFECT_COLORLOOP:
                data['effect'] = 'colorloop'
            else:
                data['effect'] = 'none'

        await self._light.async_set_state(data)

    async def async_turn_off(self, **kwargs):
        """Turn off light."""
        data = {'on': False}

        if ATTR_TRANSITION in kwargs:
            data['bri'] = 0
            data['transitiontime'] = int(kwargs[ATTR_TRANSITION]) * 10

        if ATTR_FLASH in kwargs:
            if kwargs[ATTR_FLASH] == FLASH_SHORT:
                data['alert'] = 'select'
                del data['on']
            elif kwargs[ATTR_FLASH] == FLASH_LONG:
                data['alert'] = 'lselect'
                del data['on']

        await self._light.async_set_state(data)
