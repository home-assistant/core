"""Lights on Zigbee Home Automation networks."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
import functools
import itertools
import logging
import random
from typing import TYPE_CHECKING, Any, cast

from zigpy.zcl.clusters.general import Identify, LevelControl, OnOff
from zigpy.zcl.clusters.lighting import Color
from zigpy.zcl.foundation import Status

from homeassistant.components import light
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_HS_COLOR,
    ATTR_MAX_MIREDS,
    ATTR_MIN_MIREDS,
    ATTR_SUPPORTED_COLOR_MODES,
    ColorMode,
    brightness_supported,
    filter_supported_color_modes,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.color as color_util

from .core import discovery, helpers
from .core.const import (
    CHANNEL_COLOR,
    CHANNEL_LEVEL,
    CHANNEL_ON_OFF,
    CONF_DEFAULT_LIGHT_TRANSITION,
    DATA_ZHA,
    EFFECT_BLINK,
    EFFECT_BREATHE,
    EFFECT_DEFAULT_VARIANT,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
    SIGNAL_SET_LEVEL,
    ZHA_OPTIONS,
)
from .core.helpers import LogMixin, async_get_zha_config_value
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity, ZhaGroupEntity

if TYPE_CHECKING:
    from .core.device import ZHADevice

_LOGGER = logging.getLogger(__name__)

CAPABILITIES_COLOR_LOOP = 0x4
CAPABILITIES_COLOR_XY = 0x08
CAPABILITIES_COLOR_TEMP = 0x10

DEFAULT_MIN_BRIGHTNESS = 2

UPDATE_COLORLOOP_ACTION = 0x1
UPDATE_COLORLOOP_DIRECTION = 0x2
UPDATE_COLORLOOP_TIME = 0x4
UPDATE_COLORLOOP_HUE = 0x8

FLASH_EFFECTS = {light.FLASH_SHORT: EFFECT_BLINK, light.FLASH_LONG: EFFECT_BREATHE}

UNSUPPORTED_ATTRIBUTE = 0x86
STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, Platform.LIGHT)
GROUP_MATCH = functools.partial(ZHA_ENTITIES.group_match, Platform.LIGHT)
PARALLEL_UPDATES = 0
SIGNAL_LIGHT_GROUP_STATE_CHANGED = "zha_light_group_state_changed"

COLOR_MODES_GROUP_LIGHT = {ColorMode.COLOR_TEMP, ColorMode.HS}
SUPPORT_GROUP_LIGHT = (
    light.LightEntityFeature.EFFECT
    | light.LightEntityFeature.FLASH
    | light.LightEntityFeature.TRANSITION
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation light from config entry."""
    entities_to_create = hass.data[DATA_ZHA][Platform.LIGHT]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class BaseLight(LogMixin, light.LightEntity):
    """Operations common to all light entities."""

    _FORCE_ON = False
    _DEFAULT_MIN_TRANSITION_TIME = 0

    def __init__(self, *args, **kwargs):
        """Initialize the light."""
        super().__init__(*args, **kwargs)
        self._available: bool = False
        self._brightness: int | None = None
        self._off_with_transition: bool = False
        self._off_brightness: int | None = None
        self._hs_color: tuple[float, float] | None = None
        self._color_temp: int | None = None
        self._min_mireds: int | None = 153
        self._max_mireds: int | None = 500
        self._effect_list: list[str] | None = None
        self._effect: str | None = None
        self._supported_features: int = 0
        self._state: bool = False
        self._on_off_channel = None
        self._level_channel = None
        self._color_channel = None
        self._identify_channel = None
        self._zha_config_transition = self._DEFAULT_MIN_TRANSITION_TIME
        self._attr_color_mode = ColorMode.UNKNOWN  # Set by sub classes

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return state attributes."""
        attributes = {
            "off_with_transition": self._off_with_transition,
            "off_brightness": self._off_brightness,
        }
        return attributes

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
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return self._min_mireds

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return self._max_mireds

    @callback
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

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        transition = kwargs.get(light.ATTR_TRANSITION)
        duration = (
            transition * 10
            if transition is not None
            else self._zha_config_transition * 10
        ) or self._DEFAULT_MIN_TRANSITION_TIME  # if 0 is passed in some devices still need the minimum default
        brightness = kwargs.get(light.ATTR_BRIGHTNESS)
        effect = kwargs.get(light.ATTR_EFFECT)
        flash = kwargs.get(light.ATTR_FLASH)
        temperature = kwargs.get(light.ATTR_COLOR_TEMP)
        hs_color = kwargs.get(light.ATTR_HS_COLOR)

        # If the light is currently off but a turn_on call with a color/temperature is sent,
        # the light needs to be turned on first at a low brightness level where the light is immediately transitioned
        # to the correct color. Afterwards, the transition is only from the low brightness to the new brightness.
        # Otherwise, the transition is from the color the light had before being turned on to the new color.
        # This can look especially bad with transitions longer than a second. We do not want to do this for
        # devices that need to be forced to use the on command because we would end up with 4 commands sent:
        # move to level, on, color, move to level... We also will not set this if the bulb is already in the
        # desired color mode with the desired color or color temperature.
        new_color_provided_while_off = (
            not isinstance(self, LightGroup)
            and not self._FORCE_ON
            and not self._state
            and (
                (
                    temperature is not None
                    and (
                        self._color_temp != temperature
                        or self._attr_color_mode != ColorMode.COLOR_TEMP
                    )
                )
                or (
                    hs_color is not None
                    and (
                        self.hs_color != hs_color
                        or self._attr_color_mode != ColorMode.HS
                    )
                )
            )
            and brightness_supported(self._attr_supported_color_modes)
        )

        if (
            brightness is None
            and (self._off_with_transition or new_color_provided_while_off)
            and self._off_brightness is not None
        ):
            brightness = self._off_brightness

        if brightness is not None:
            level = min(254, brightness)
        else:
            level = self._brightness or 254

        t_log = {}

        if new_color_provided_while_off:
            # If the light is currently off, we first need to turn it on at a low brightness level with no transition.
            # After that, we set it to the desired color/temperature with no transition.
            result = await self._level_channel.move_to_level_with_on_off(
                DEFAULT_MIN_BRIGHTNESS, self._DEFAULT_MIN_TRANSITION_TIME
            )
            t_log["move_to_level_with_on_off"] = result
            if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
                self.debug("turned on: %s", t_log)
                return
            # Currently only setting it to "on", as the correct level state will be set at the second move_to_level call
            self._state = True

        if (
            (brightness is not None or transition)
            and not new_color_provided_while_off
            and brightness_supported(self._attr_supported_color_modes)
        ):
            result = await self._level_channel.move_to_level_with_on_off(
                level, duration
            )
            t_log["move_to_level_with_on_off"] = result
            if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
                self.debug("turned on: %s", t_log)
                return
            self._state = bool(level)
            if level:
                self._brightness = level

        if (
            brightness is None
            and not new_color_provided_while_off
            or (self._FORCE_ON and brightness)
        ):
            # since some lights don't always turn on with move_to_level_with_on_off,
            # we should call the on command on the on_off cluster if brightness is not 0.
            result = await self._on_off_channel.on()
            t_log["on_off"] = result
            if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
                self.debug("turned on: %s", t_log)
                return
            self._state = True

        if temperature is not None:
            result = await self._color_channel.move_to_color_temp(
                temperature,
                self._DEFAULT_MIN_TRANSITION_TIME
                if new_color_provided_while_off
                else duration,
            )
            t_log["move_to_color_temp"] = result
            if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
                self.debug("turned on: %s", t_log)
                return
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._color_temp = temperature
            self._hs_color = None

        if hs_color is not None:
            xy_color = color_util.color_hs_to_xy(*hs_color)
            result = await self._color_channel.move_to_color(
                int(xy_color[0] * 65535),
                int(xy_color[1] * 65535),
                self._DEFAULT_MIN_TRANSITION_TIME
                if new_color_provided_while_off
                else duration,
            )
            t_log["move_to_color"] = result
            if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
                self.debug("turned on: %s", t_log)
                return
            self._attr_color_mode = ColorMode.HS
            self._hs_color = hs_color
            self._color_temp = None

        if new_color_provided_while_off:
            # The light is has the correct color, so we can now transition it to the correct brightness level.
            result = await self._level_channel.move_to_level(level, duration)
            t_log["move_to_level_if_color"] = result
            if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
                self.debug("turned on: %s", t_log)
                return
            self._state = bool(level)
            if level:
                self._brightness = level

        if effect == light.EFFECT_COLORLOOP:
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
            self._effect == light.EFFECT_COLORLOOP and effect != light.EFFECT_COLORLOOP
        ):
            result = await self._color_channel.color_loop_set(
                UPDATE_COLORLOOP_ACTION,
                0x0,
                0x0,
                0x0,
                0x0,  # update action only, action off, no dir, time, hue
            )
            t_log["color_loop_set"] = result
            self._effect = None

        if flash is not None:
            result = await self._identify_channel.trigger_effect(
                FLASH_EFFECTS[flash], EFFECT_DEFAULT_VARIANT
            )
            t_log["trigger_effect"] = result

        self._off_with_transition = False
        self._off_brightness = None
        self.debug("turned on: %s", t_log)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        transition = kwargs.get(light.ATTR_TRANSITION)
        supports_level = brightness_supported(self._attr_supported_color_modes)

        # is not none looks odd here but it will override built in bulb transition times if we pass 0 in here
        if transition is not None and supports_level:
            result = await self._level_channel.move_to_level_with_on_off(
                0, transition * 10
            )
        else:
            result = await self._on_off_channel.off()
        self.debug("turned off: %s", result)
        if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
            return
        self._state = False

        if supports_level:
            # store current brightness so that the next turn_on uses it.
            self._off_with_transition = transition is not None
            self._off_brightness = self._brightness

        self.async_write_ha_state()


@STRICT_MATCH(channel_names=CHANNEL_ON_OFF, aux_channels={CHANNEL_COLOR, CHANNEL_LEVEL})
class Light(BaseLight, ZhaEntity):
    """Representation of a ZHA or ZLL light."""

    _attr_supported_color_modes: set[ColorMode]
    _REFRESH_INTERVAL = (45, 75)

    def __init__(self, unique_id, zha_device: ZHADevice, channels, **kwargs):
        """Initialize the ZHA light."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._on_off_channel = self.cluster_channels[CHANNEL_ON_OFF]
        self._state = bool(self._on_off_channel.on_off)
        self._level_channel = self.cluster_channels.get(CHANNEL_LEVEL)
        self._color_channel = self.cluster_channels.get(CHANNEL_COLOR)
        self._identify_channel = self.zha_device.channels.identify_ch
        if self._color_channel:
            self._min_mireds: int | None = self._color_channel.min_mireds
            self._max_mireds: int | None = self._color_channel.max_mireds
        self._cancel_refresh_handle = None
        effect_list = []

        self._attr_supported_color_modes = {ColorMode.ONOFF}
        if self._level_channel:
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
            self._supported_features |= light.LightEntityFeature.TRANSITION
            self._brightness = self._level_channel.current_level

        if self._color_channel:
            color_capabilities = self._color_channel.color_capabilities
            if color_capabilities & CAPABILITIES_COLOR_TEMP:
                self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
                self._color_temp = self._color_channel.color_temperature

            if color_capabilities & CAPABILITIES_COLOR_XY:
                self._attr_supported_color_modes.add(ColorMode.HS)
                curr_x = self._color_channel.current_x
                curr_y = self._color_channel.current_y
                if curr_x is not None and curr_y is not None:
                    self._hs_color = color_util.color_xy_to_hs(
                        float(curr_x / 65535), float(curr_y / 65535)
                    )
                else:
                    self._hs_color = (0, 0)

            if color_capabilities & CAPABILITIES_COLOR_LOOP:
                self._supported_features |= light.LightEntityFeature.EFFECT
                effect_list.append(light.EFFECT_COLORLOOP)
                if self._color_channel.color_loop_active == 1:
                    self._effect = light.EFFECT_COLORLOOP
        self._attr_supported_color_modes = filter_supported_color_modes(
            self._attr_supported_color_modes
        )
        if len(self._attr_supported_color_modes) == 1:
            self._attr_color_mode = next(iter(self._attr_supported_color_modes))
        else:  # Light supports color_temp + hs, determine which mode the light is in
            assert self._color_channel
            if self._color_channel.color_mode == Color.ColorMode.Color_temperature:
                self._attr_color_mode = ColorMode.COLOR_TEMP
            else:
                self._attr_color_mode = ColorMode.HS

        if self._identify_channel:
            self._supported_features |= light.LightEntityFeature.FLASH

        if effect_list:
            self._effect_list = effect_list

        self._zha_config_transition = async_get_zha_config_value(
            zha_device.gateway.config_entry,
            ZHA_OPTIONS,
            CONF_DEFAULT_LIGHT_TRANSITION,
            0,
        )

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Set the state."""
        self._state = bool(value)
        if value:
            self._off_with_transition = False
            self._off_brightness = None
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._on_off_channel, SIGNAL_ATTR_UPDATED, self.async_set_state
        )
        if self._level_channel:
            self.async_accept_signal(
                self._level_channel, SIGNAL_SET_LEVEL, self.set_level
            )
        refresh_interval = random.randint(*(x * 60 for x in self._REFRESH_INTERVAL))
        self._cancel_refresh_handle = async_track_time_interval(
            self.hass, self._refresh, timedelta(seconds=refresh_interval)
        )
        self.async_accept_signal(
            None,
            SIGNAL_LIGHT_GROUP_STATE_CHANGED,
            self._maybe_force_refresh,
            signal_override=True,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect entity object when removed."""
        assert self._cancel_refresh_handle
        self._cancel_refresh_handle()
        await super().async_will_remove_from_hass()

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._state = last_state.state == STATE_ON
        if "brightness" in last_state.attributes:
            self._brightness = last_state.attributes["brightness"]
        if "off_with_transition" in last_state.attributes:
            self._off_with_transition = last_state.attributes["off_with_transition"]
        if "off_brightness" in last_state.attributes:
            self._off_brightness = last_state.attributes["off_brightness"]
        if "color_mode" in last_state.attributes:
            self._attr_color_mode = ColorMode(last_state.attributes["color_mode"])
        if "color_temp" in last_state.attributes:
            self._color_temp = last_state.attributes["color_temp"]
        if "hs_color" in last_state.attributes:
            self._hs_color = last_state.attributes["hs_color"]
        if "effect" in last_state.attributes:
            self._effect = last_state.attributes["effect"]

    async def async_get_state(self):
        """Attempt to retrieve the state from the light."""
        if not self.available:
            return
        self.debug("polling current state")
        if self._on_off_channel:
            state = await self._on_off_channel.get_attribute_value(
                "on_off", from_cache=False
            )
            if state is not None:
                self._state = state
        if self._level_channel:
            level = await self._level_channel.get_attribute_value(
                "current_level", from_cache=False
            )
            if level is not None:
                self._brightness = level
        if self._color_channel:
            attributes = [
                "color_mode",
                "color_temperature",
                "current_x",
                "current_y",
                "color_loop_active",
            ]

            results = await self._color_channel.get_attributes(
                attributes, from_cache=False, only_cache=False
            )

            if (color_mode := results.get("color_mode")) is not None:
                if color_mode == Color.ColorMode.Color_temperature:
                    self._attr_color_mode = ColorMode.COLOR_TEMP
                    color_temp = results.get("color_temperature")
                    if color_temp is not None and color_mode:
                        self._color_temp = color_temp
                        self._hs_color = None
                else:
                    self._attr_color_mode = ColorMode.HS
                    color_x = results.get("current_x")
                    color_y = results.get("current_y")
                    if color_x is not None and color_y is not None:
                        self._hs_color = color_util.color_xy_to_hs(
                            float(color_x / 65535), float(color_y / 65535)
                        )
                        self._color_temp = None

            color_loop_active = results.get("color_loop_active")
            if color_loop_active is not None:
                if color_loop_active == 1:
                    self._effect = light.EFFECT_COLORLOOP
                else:
                    self._effect = None

    async def async_update(self):
        """Update to the latest state."""
        await self.async_get_state()

    async def _refresh(self, time):
        """Call async_get_state at an interval."""
        await self.async_get_state()
        self.async_write_ha_state()

    async def _maybe_force_refresh(self, signal):
        """Force update the state if the signal contains the entity id for this entity."""
        if self.entity_id in signal["entity_ids"]:
            await self.async_get_state()
            self.async_write_ha_state()


@STRICT_MATCH(
    channel_names=CHANNEL_ON_OFF,
    aux_channels={CHANNEL_COLOR, CHANNEL_LEVEL},
    manufacturers={"Philips", "Signify Netherlands B.V."},
)
class HueLight(Light):
    """Representation of a HUE light which does not report attributes."""

    _REFRESH_INTERVAL = (3, 5)


@STRICT_MATCH(
    channel_names=CHANNEL_ON_OFF,
    aux_channels={CHANNEL_COLOR, CHANNEL_LEVEL},
    manufacturers={"Jasco", "Quotra-Vision", "eWeLight", "eWeLink"},
)
class ForceOnLight(Light):
    """Representation of a light which does not respect move_to_level_with_on_off."""

    _FORCE_ON = True


@STRICT_MATCH(
    channel_names=CHANNEL_ON_OFF,
    aux_channels={CHANNEL_COLOR, CHANNEL_LEVEL},
    manufacturers={"Sengled"},
)
class SengledLight(Light):
    """Representation of a Sengled light which does not react to move_to_color_temp with 0 as a transition."""

    _DEFAULT_MIN_TRANSITION_TIME = 1


@GROUP_MATCH()
class LightGroup(BaseLight, ZhaGroupEntity):
    """Representation of a light group."""

    def __init__(
        self, entity_ids: list[str], unique_id: str, group_id: int, zha_device, **kwargs
    ) -> None:
        """Initialize a light group."""
        super().__init__(entity_ids, unique_id, group_id, zha_device, **kwargs)
        group = self.zha_device.gateway.get_group(self._group_id)
        self._on_off_channel = group.endpoint[OnOff.cluster_id]
        self._level_channel = group.endpoint[LevelControl.cluster_id]
        self._color_channel = group.endpoint[Color.cluster_id]
        self._identify_channel = group.endpoint[Identify.cluster_id]
        self._debounced_member_refresh = None
        self._zha_config_transition = async_get_zha_config_value(
            zha_device.gateway.config_entry,
            ZHA_OPTIONS,
            CONF_DEFAULT_LIGHT_TRANSITION,
            0,
        )
        self._attr_color_mode = None

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        if self._debounced_member_refresh is None:
            force_refresh_debouncer = Debouncer(
                self.hass,
                _LOGGER,
                cooldown=3,
                immediate=True,
                function=self._force_member_updates,
            )
            self._debounced_member_refresh = force_refresh_debouncer

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await super().async_turn_on(**kwargs)
        await self._debounced_member_refresh.async_call()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await super().async_turn_off(**kwargs)
        await self._debounced_member_refresh.async_call()

    async def async_update(self) -> None:
        """Query all members and determine the light group state."""
        all_states = [self.hass.states.get(x) for x in self._entity_ids]
        states: list[State] = list(filter(None, all_states))
        on_states = [state for state in states if state.state == STATE_ON]

        self._state = len(on_states) > 0
        self._available = any(state.state != STATE_UNAVAILABLE for state in states)

        self._brightness = helpers.reduce_attribute(on_states, ATTR_BRIGHTNESS)

        self._hs_color = helpers.reduce_attribute(
            on_states, ATTR_HS_COLOR, reduce=helpers.mean_tuple
        )

        self._color_temp = helpers.reduce_attribute(on_states, ATTR_COLOR_TEMP)
        self._min_mireds = helpers.reduce_attribute(
            states, ATTR_MIN_MIREDS, default=153, reduce=min
        )
        self._max_mireds = helpers.reduce_attribute(
            states, ATTR_MAX_MIREDS, default=500, reduce=max
        )

        self._effect_list = None
        all_effect_lists = list(helpers.find_state_attributes(states, ATTR_EFFECT_LIST))
        if all_effect_lists:
            # Merge all effects from all effect_lists with a union merge.
            self._effect_list = list(set().union(*all_effect_lists))

        self._effect = None
        all_effects = list(helpers.find_state_attributes(on_states, ATTR_EFFECT))
        if all_effects:
            # Report the most common effect.
            effects_count = Counter(itertools.chain(all_effects))
            self._effect = effects_count.most_common(1)[0][0]

        self._attr_color_mode = None
        all_color_modes = list(
            helpers.find_state_attributes(on_states, ATTR_COLOR_MODE)
        )
        if all_color_modes:
            # Report the most common color mode, select brightness and onoff last
            color_mode_count = Counter(itertools.chain(all_color_modes))
            if ColorMode.ONOFF in color_mode_count:
                color_mode_count[ColorMode.ONOFF] = -1
            if ColorMode.BRIGHTNESS in color_mode_count:
                color_mode_count[ColorMode.BRIGHTNESS] = 0
            self._attr_color_mode = color_mode_count.most_common(1)[0][0]

        self._attr_supported_color_modes = None
        all_supported_color_modes = list(
            helpers.find_state_attributes(states, ATTR_SUPPORTED_COLOR_MODES)
        )
        if all_supported_color_modes:
            # Merge all color modes.
            self._attr_supported_color_modes = cast(
                set[str], set().union(*all_supported_color_modes)
            )

        self._supported_features = 0
        for support in helpers.find_state_attributes(states, ATTR_SUPPORTED_FEATURES):
            # Merge supported features by emulating support for every feature
            # we find.
            self._supported_features |= support
        # Bitwise-and the supported features with the GroupedLight's features
        # so that we don't break in the future when a new feature is added.
        self._supported_features &= SUPPORT_GROUP_LIGHT

    async def _force_member_updates(self):
        """Force the update of member entities to ensure the states are correct for bulbs that don't report their state."""
        async_dispatcher_send(
            self.hass,
            SIGNAL_LIGHT_GROUP_STATE_CHANGED,
            {"entity_ids": self._entity_ids},
        )
