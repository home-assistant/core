"""Lights on Zigbee Home Automation networks."""
from datetime import timedelta
import functools
import logging
import random

from zigpy.zcl.foundation import Status

from homeassistant.components import light
from homeassistant.const import STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.color as color_util

from .core import discovery
from .core.const import (
    CHANNEL_COLOR,
    CHANNEL_LEVEL,
    CHANNEL_ON_OFF,
    DATA_ZHA,
    DATA_ZHA_DISPATCHERS,
    EFFECT_BLINK,
    EFFECT_BREATHE,
    EFFECT_DEFAULT_VARIANT,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
    SIGNAL_SET_LEVEL,
)
from .core.registries import ZHA_ENTITIES
from .core.typing import ZhaDeviceType
from .entity import ZhaEntity

_LOGGER = logging.getLogger(__name__)

CAPABILITIES_COLOR_LOOP = 0x4
CAPABILITIES_COLOR_XY = 0x08
CAPABILITIES_COLOR_TEMP = 0x10

UPDATE_COLORLOOP_ACTION = 0x1
UPDATE_COLORLOOP_DIRECTION = 0x2
UPDATE_COLORLOOP_TIME = 0x4
UPDATE_COLORLOOP_HUE = 0x8

FLASH_EFFECTS = {light.FLASH_SHORT: EFFECT_BLINK, light.FLASH_LONG: EFFECT_BREATHE}

UNSUPPORTED_ATTRIBUTE = 0x86
STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, light.DOMAIN)
PARALLEL_UPDATES = 0
_REFRESH_INTERVAL = (45, 75)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation light from config entry."""
    entities_to_create = hass.data[DATA_ZHA][light.DOMAIN] = []

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)


@STRICT_MATCH(channel_names=CHANNEL_ON_OFF, aux_channels={CHANNEL_COLOR, CHANNEL_LEVEL})
class Light(ZhaEntity, light.Light):
    """Representation of a ZHA or ZLL light."""

    def __init__(self, unique_id, zha_device: ZhaDeviceType, channels, **kwargs):
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
        self._identify_channel = self.zha_device.channels.identify_ch
        self._cancel_refresh_handle = None

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

        if self._identify_channel:
            self._supported_features |= light.SUPPORT_FLASH

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
        self.async_write_ha_state()

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
    def async_set_state(self, attr_id, attr_name, value):
        """Set the state."""
        self._state = bool(value)
        if value:
            self._off_brightness = None
        self.async_write_ha_state()

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
        refresh_interval = random.randint(*_REFRESH_INTERVAL)
        self._cancel_refresh_handle = async_track_time_interval(
            self.hass, self._refresh, timedelta(minutes=refresh_interval)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect entity object when removed."""
        self._cancel_refresh_handle()
        await super().async_will_remove_from_hass()

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
        flash = kwargs.get(light.ATTR_FLASH)

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

        if flash is not None and self._supported_features & light.SUPPORT_FLASH:
            result = await self._identify_channel.trigger_effect(
                FLASH_EFFECTS[flash], EFFECT_DEFAULT_VARIANT
            )
            t_log["trigger_effect"] = result

        self._off_brightness = None
        self.debug("turned on: %s", t_log)
        self.async_write_ha_state()

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

        self.async_write_ha_state()

    async def async_update(self):
        """Attempt to retrieve on off state from the light."""
        await super().async_update()
        await self.async_get_state()

    async def async_get_state(self, from_cache=True):
        """Attempt to retrieve on off state from the light."""
        self.debug("polling current state")
        if self._on_off_channel:
            state = await self._on_off_channel.get_attribute_value(
                "on_off", from_cache=from_cache
            )
            if state is not None:
                self._state = state
        if self._level_channel:
            level = await self._level_channel.get_attribute_value(
                "current_level", from_cache=from_cache
            )
            if level is not None:
                self._brightness = level
        if self._color_channel:
            attributes = []
            color_capabilities = self._color_channel.get_color_capabilities()
            if (
                color_capabilities is not None
                and color_capabilities & CAPABILITIES_COLOR_TEMP
            ):
                attributes.append("color_temperature")
            if (
                color_capabilities is not None
                and color_capabilities & CAPABILITIES_COLOR_XY
            ):
                attributes.append("current_x")
                attributes.append("current_y")
            if (
                color_capabilities is not None
                and color_capabilities & CAPABILITIES_COLOR_LOOP
            ):
                attributes.append("color_loop_active")

            results = await self._color_channel.get_attributes(
                attributes, from_cache=from_cache
            )

            if (
                "color_temperature" in results
                and results["color_temperature"] is not None
            ):
                self._color_temp = results["color_temperature"]

            color_x = results.get("color_x")
            color_y = results.get("color_y")
            if color_x is not None and color_y is not None:
                self._hs_color = color_util.color_xy_to_hs(
                    float(color_x / 65535), float(color_y / 65535)
                )
            if (
                "color_loop_active" in results
                and results["color_loop_active"] is not None
            ):
                color_loop_active = results["color_loop_active"]
                if color_loop_active == 1:
                    self._effect = light.EFFECT_COLORLOOP

    async def _refresh(self, time):
        """Call async_get_state at an interval."""
        await self.async_get_state(from_cache=False)
        self.async_write_ha_state()
