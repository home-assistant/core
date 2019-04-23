"""
Lights on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/light.zha/
"""
from datetime import timedelta
import logging

from homeassistant.components import light
from homeassistant.const import STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.color as color_util
from .const import (
    DATA_ZHA, DATA_ZHA_DISPATCHERS, ZHA_DISCOVERY_NEW, COLOR_CHANNEL,
    ON_OFF_CHANNEL, LEVEL_CHANNEL, SIGNAL_ATTR_UPDATED, SIGNAL_SET_LEVEL
    )
from .entity import ZhaEntity


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha']

DEFAULT_DURATION = 5

CAPABILITIES_COLOR_XY = 0x08
CAPABILITIES_COLOR_TEMP = 0x10

UNSUPPORTED_ATTRIBUTE = 0x86
SCAN_INTERVAL = timedelta(minutes=60)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Old way of setting up Zigbee Home Automation lights."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation light from config entry."""
    async def async_discover(discovery_info):
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    [discovery_info])

    unsub = async_dispatcher_connect(
        hass, ZHA_DISCOVERY_NEW.format(light.DOMAIN), async_discover)
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)

    lights = hass.data.get(DATA_ZHA, {}).get(light.DOMAIN)
    if lights is not None:
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    lights.values())
        del hass.data[DATA_ZHA][light.DOMAIN]


async def _async_setup_entities(hass, config_entry, async_add_entities,
                                discovery_infos):
    """Set up the ZHA lights."""
    entities = []
    for discovery_info in discovery_infos:
        zha_light = Light(**discovery_info)
        entities.append(zha_light)

    async_add_entities(entities, update_before_add=True)


class Light(ZhaEntity, light.Light):
    """Representation of a ZHA or ZLL light."""

    _domain = light.DOMAIN

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Initialize the ZHA light."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._supported_features = 0
        self._color_temp = None
        self._hs_color = None
        self._brightness = None
        self._on_off_channel = self.cluster_channels.get(ON_OFF_CHANNEL)
        self._level_channel = self.cluster_channels.get(LEVEL_CHANNEL)
        self._color_channel = self.cluster_channels.get(COLOR_CHANNEL)

        if self._level_channel:
            self._supported_features |= light.SUPPORT_BRIGHTNESS
            self._supported_features |= light.SUPPORT_TRANSITION
            self._brightness = 0

        if self._color_channel:
            color_capabilities = self._color_channel.get_color_capabilities()
            if color_capabilities & CAPABILITIES_COLOR_TEMP:
                self._supported_features |= light.SUPPORT_COLOR_TEMP

            if color_capabilities & CAPABILITIES_COLOR_XY:
                self._supported_features |= light.SUPPORT_COLOR
                self._hs_color = (0, 0)

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        if self._state is None:
            return False
        return self._state

    @property
    def brightness(self):
        """Return the brightness of this light."""
        return self._brightness

    @property
    def device_state_attributes(self):
        """Return state attributes."""
        return self.state_attributes

    def set_level(self, value):
        """Set the brightness of this light between 0..254.

        brightness level 255 is a special value instructing the device to come
        on at `on_level` Zigbee attribute value, regardless of the last set
        level
        """
        value = max(0, min(254, value))
        self._brightness = value
        self.async_schedule_update_ha_state()

    @property
    def hs_color(self):
        """Return the hs color value [int, int]."""
        return self._hs_color

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        return self._color_temp

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    def async_set_state(self, state):
        """Set the state."""
        self._state = bool(state)
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        await self.async_accept_signal(
            self._on_off_channel, SIGNAL_ATTR_UPDATED, self.async_set_state)
        if self._level_channel:
            await self.async_accept_signal(
                self._level_channel, SIGNAL_SET_LEVEL, self.set_level)
        async_track_time_interval(self.hass, self.refresh, SCAN_INTERVAL)

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._state = last_state.state == STATE_ON
        if 'brightness' in last_state.attributes:
            self._brightness = last_state.attributes['brightness']
        if 'color_temp' in last_state.attributes:
            self._color_temp = last_state.attributes['color_temp']
        if 'hs_color' in last_state.attributes:
            self._hs_color = last_state.attributes['hs_color']

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        transition = kwargs.get(light.ATTR_TRANSITION)
        duration = transition * 10 if transition else DEFAULT_DURATION
        brightness = kwargs.get(light.ATTR_BRIGHTNESS)

        t_log = {}
        if (brightness is not None or transition) and \
                self._supported_features & light.SUPPORT_BRIGHTNESS:
            if brightness is not None:
                level = min(254, brightness)
            else:
                level = self._brightness or 254
            success = await self._level_channel.move_to_level_with_on_off(
                level,
                duration
            )
            t_log['move_to_level_with_on_off'] = success
            if not success:
                self.debug("turned on: %s", t_log)
                return
            self._state = bool(level)
            if level:
                self._brightness = level

        if brightness is None or brightness:
            success = await self._on_off_channel.on()
            t_log['on_off'] = success
            if not success:
                self.debug("turned on: %s", t_log)
                return
            self._state = True

        if light.ATTR_COLOR_TEMP in kwargs and \
                self.supported_features & light.SUPPORT_COLOR_TEMP:
            temperature = kwargs[light.ATTR_COLOR_TEMP]
            success = await self._color_channel.move_to_color_temp(
                temperature, duration)
            t_log['move_to_color_temp'] = success
            if not success:
                self.debug("turned on: %s", t_log)
                return
            self._color_temp = temperature

        if light.ATTR_HS_COLOR in kwargs and \
                self.supported_features & light.SUPPORT_COLOR:
            hs_color = kwargs[light.ATTR_HS_COLOR]
            xy_color = color_util.color_hs_to_xy(*hs_color)
            success = await self._color_channel.move_to_color(
                int(xy_color[0] * 65535),
                int(xy_color[1] * 65535),
                duration,
            )
            t_log['move_to_color'] = success
            if not success:
                self.debug("turned on: %s", t_log)
                return
            self._hs_color = hs_color

        self.debug("turned on: %s", t_log)
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        duration = kwargs.get(light.ATTR_TRANSITION)
        supports_level = self.supported_features & light.SUPPORT_BRIGHTNESS
        if duration and supports_level:
            success = await self._level_channel.move_to_level_with_on_off(
                0,
                duration*10
            )
        else:
            success = await self._on_off_channel.off()
        self.debug("turned off: %s", success)
        if not success:
            return
        self._state = False
        self.async_schedule_update_ha_state()

    async def async_update(self):
        """Attempt to retrieve on off state from the light."""
        await super().async_update()
        await self.async_get_state()

    async def async_get_state(self, from_cache=True):
        """Attempt to retrieve on off state from the light."""
        if self._on_off_channel:
            self._state = await self._on_off_channel.get_attribute_value(
                'on_off', from_cache=from_cache)
        if self._level_channel:
            self._brightness = await self._level_channel.get_attribute_value(
                'current_level', from_cache=from_cache)

    async def refresh(self, time):
        """Call async_get_state at an interval."""
        await self.async_get_state(from_cache=False)

    def debug(self, msg, *args):
        """Log debug message."""
        _LOGGER.debug('%s: ' + msg, self.entity_id, *args)
