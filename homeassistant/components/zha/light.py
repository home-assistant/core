"""Lights on Zigbee Home Automation networks."""
from datetime import timedelta
import functools
import logging

from zigpy.zcl.foundation import Status

from homeassistant.components import light
from homeassistant.const import STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.color as color_util

from .core.const import (
    CHANNEL_COLOR,
    CHANNEL_LEVEL,
    CHANNEL_ON_OFF,
    DATA_ZHA,
    DATA_ZHA_DISPATCHERS,
    SIGNAL_ATTR_UPDATED,
    SIGNAL_SET_LEVEL,
    ZHA_DISCOVERY_NEW,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

_LOGGER = logging.getLogger(__name__)

CAPABILITIES_COLOR_LOOP = 0x4
CAPABILITIES_COLOR_XY = 0x08
CAPABILITIES_COLOR_TEMP = 0x10

UPDATE_COLORLOOP_ACTION = 0x1
UPDATE_COLORLOOP_DIRECTION = 0x2
UPDATE_COLORLOOP_TIME = 0x4
UPDATE_COLORLOOP_HUE = 0x8

UNSUPPORTED_ATTRIBUTE = 0x86
SCAN_INTERVAL = timedelta(minutes=60)
STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, light.DOMAIN)
PARALLEL_UPDATES = 5


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation light from config entry."""

    async def async_discover(discovery_info):
        await _async_setup_entities(
            hass, config_entry, async_add_entities, [discovery_info]
        )

    unsub = async_dispatcher_connect(
        hass, ZHA_DISCOVERY_NEW.format(light.DOMAIN), async_discover
    )
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)

    lights = hass.data.get(DATA_ZHA, {}).get(light.DOMAIN)
    if lights is not None:
        await _async_setup_entities(
            hass, config_entry, async_add_entities, lights.values()
        )
        del hass.data[DATA_ZHA][light.DOMAIN]


async def _async_setup_entities(
    hass, config_entry, async_add_entities, discovery_infos
):
    """Set up the ZHA lights."""
    entities = []
    for discovery_info in discovery_infos:
        zha_dev = discovery_info["zha_device"]
        channels = discovery_info["channels"]

        entity = ZHA_ENTITIES.get_entity(light.DOMAIN, zha_dev, channels, Light)
        if entity:
            entities.append(entity(**discovery_info))

    if entities:
        async_add_entities(entities, update_before_add=True)


@STRICT_MATCH(channel_names=CHANNEL_ON_OFF)
class Light(ZhaEntity, light.Light):
    """Representation of a ZHA or ZLL light."""

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Initialize the ZHA light."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._supported_features = 0
        self._color_temp = None
        self._hs_color = None
        self._brightness = None
        self._off_brightness = None
        self._effect_list = []
        self._effect = None
        self._on_off_channel = self.cluster_channels.get(CHANNEL_ON_OFF)
        self._level_channel = self.cluster_channels.get(CHANNEL_LEVEL)
        self._color_channel = self.cluster_channels.get(CHANNEL_COLOR)

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

            if color_capabilities & CAPABILITIES_COLOR_LOOP:
                self._supported_features |= light.SUPPORT_EFFECT
                self._effect_list.append(light.EFFECT_COLORLOOP)

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
        attributes = {"off_brightness": self._off_brightness}
        return attributes

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
    def effect_list(self):
        """Return the list of supported effects."""
        return self._effect_list

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    @callback
    def async_set_state(self, state):
        """Set the state."""
        self._state = bool(state)
        if state:
            self._off_brightness = None
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        await self.async_accept_signal(
            self._on_off_channel, SIGNAL_ATTR_UPDATED, self.async_set_state
        )
        if self._level_channel:
            await self.async_accept_signal(
                self._level_channel, SIGNAL_SET_LEVEL, self.set_level
            )
        async_track_time_interval(self.hass, self.refresh, SCAN_INTERVAL)

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._state = last_state.state == STATE_ON
        if "brightness" in last_state.attributes:
            self._brightness = last_state.attributes["brightness"]
        if "off_brightness" in last_state.attributes:
            self._off_brightness = last_state.attributes["off_brightness"]
        if "color_temp" in last_state.attributes:
            self._color_temp = last_state.attributes["color_temp"]
        if "hs_color" in last_state.attributes:
            self._hs_color = last_state.attributes["hs_color"]
        if "effect" in last_state.attributes:
            self._effect = last_state.attributes["effect"]

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        transition = kwargs.get(light.ATTR_TRANSITION)
        duration = transition * 10 if transition else 0
        brightness = kwargs.get(light.ATTR_BRIGHTNESS)
        effect = kwargs.get(light.ATTR_EFFECT)

        if brightness is None and self._off_brightness is not None:
            brightness = self._off_brightness

        t_log = {}
        if (
            brightness is not None or transition
        ) and self._supported_features & light.SUPPORT_BRIGHTNESS:
            if brightness is not None:
                level = min(254, brightness)
            else:
                level = self._brightness or 254
            result = await self._level_channel.move_to_level_with_on_off(
                level, duration
            )
            t_log["move_to_level_with_on_off"] = result
            if not isinstance(result, list) or result[1] is not Status.SUCCESS:
                self.debug("turned on: %s", t_log)
                return
            self._state = bool(level)
            if level:
                self._brightness = level

        if brightness is None or brightness:
            # since some lights don't always turn on with move_to_level_with_on_off,
            # we should call the on command on the on_off cluster if brightness is not 0.
            result = await self._on_off_channel.on()
            t_log["on_off"] = result
            if not isinstance(result, list) or result[1] is not Status.SUCCESS:
                self.debug("turned on: %s", t_log)
                return
            self._state = True
        if (
            light.ATTR_COLOR_TEMP in kwargs
            and self.supported_features & light.SUPPORT_COLOR_TEMP
        ):
            temperature = kwargs[light.ATTR_COLOR_TEMP]
            result = await self._color_channel.move_to_color_temp(temperature, duration)
            t_log["move_to_color_temp"] = result
            if not isinstance(result, list) or result[1] is not Status.SUCCESS:
                self.debug("turned on: %s", t_log)
                return
            self._color_temp = temperature

        if (
            light.ATTR_HS_COLOR in kwargs
            and self.supported_features & light.SUPPORT_COLOR
        ):
            hs_color = kwargs[light.ATTR_HS_COLOR]
            xy_color = color_util.color_hs_to_xy(*hs_color)
            result = await self._color_channel.move_to_color(
                int(xy_color[0] * 65535), int(xy_color[1] * 65535), duration
            )
            t_log["move_to_color"] = result
            if not isinstance(result, list) or result[1] is not Status.SUCCESS:
                self.debug("turned on: %s", t_log)
                return
            self._hs_color = hs_color

        if (
            effect == light.EFFECT_COLORLOOP
            and self.supported_features & light.SUPPORT_EFFECT
        ):
            result = await self._color_channel.color_loop_set(
                UPDATE_COLORLOOP_ACTION
                | UPDATE_COLORLOOP_DIRECTION
                | UPDATE_COLORLOOP_TIME,
                0x2,  # start from current hue
                0x1,  # only support up
                transition if transition else 7,  # transition
                0,  # no hue
            )
            t_log["color_loop_set"] = result
            self._effect = light.EFFECT_COLORLOOP
        elif (
            self._effect == light.EFFECT_COLORLOOP
            and effect != light.EFFECT_COLORLOOP
            and self.supported_features & light.SUPPORT_EFFECT
        ):
            result = await self._color_channel.color_loop_set(
                UPDATE_COLORLOOP_ACTION,
                0x0,
                0x0,
                0x0,
                0x0,  # update action only, action off, no dir,time,hue
            )
            t_log["color_loop_set"] = result
            self._effect = None

        self._off_brightness = None
        self.debug("turned on: %s", t_log)
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        duration = kwargs.get(light.ATTR_TRANSITION)
        supports_level = self.supported_features & light.SUPPORT_BRIGHTNESS

        if duration and supports_level:
            result = await self._level_channel.move_to_level_with_on_off(
                0, duration * 10
            )
        else:
            result = await self._on_off_channel.off()
        self.debug("turned off: %s", result)
        if not isinstance(result, list) or result[1] is not Status.SUCCESS:
            return
        self._state = False

        if duration and supports_level:
            # store current brightness so that the next turn_on uses it.
            self._off_brightness = self._brightness

        self.async_schedule_update_ha_state()

    async def async_update(self):
        """Attempt to retrieve on off state from the light."""
        await super().async_update()
        await self.async_get_state()

    async def async_get_state(self, from_cache=True):
        """Attempt to retrieve on off state from the light."""
        self.debug("polling current state")
        if self._on_off_channel:
            self._state = await self._on_off_channel.get_attribute_value(
                "on_off", from_cache=from_cache
            )
        if self._level_channel:
            self._brightness = await self._level_channel.get_attribute_value(
                "current_level", from_cache=from_cache
            )
        if self._color_channel:
            color_capabilities = self._color_channel.get_color_capabilities()
            if (
                color_capabilities is not None
                and color_capabilities & CAPABILITIES_COLOR_TEMP
            ):
                self._color_temp = await self._color_channel.get_attribute_value(
                    "color_temperature", from_cache=from_cache
                )
            if (
                color_capabilities is not None
                and color_capabilities & CAPABILITIES_COLOR_XY
            ):
                color_x = await self._color_channel.get_attribute_value(
                    "current_x", from_cache=from_cache
                )
                color_y = await self._color_channel.get_attribute_value(
                    "current_y", from_cache=from_cache
                )
                if color_x is not None and color_y is not None:
                    self._hs_color = color_util.color_xy_to_hs(
                        float(color_x / 65535), float(color_y / 65535)
                    )
            if (
                color_capabilities is not None
                and color_capabilities & CAPABILITIES_COLOR_LOOP
            ):
                color_loop_active = await self._color_channel.get_attribute_value(
                    "color_loop_active", from_cache=from_cache
                )
                if color_loop_active is not None and color_loop_active == 1:
                    self._effect = light.EFFECT_COLORLOOP

    async def refresh(self, time):
        """Call async_get_state at an interval."""
        await self.async_get_state(from_cache=False)
