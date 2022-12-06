"""Lights on Zigbee Home Automation networks."""
from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Callable
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
    ColorMode,
    LightEntityFeature,
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
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, State, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .core import discovery, helpers
from .core.const import (
    CHANNEL_COLOR,
    CHANNEL_LEVEL,
    CHANNEL_ON_OFF,
    CONF_ALWAYS_PREFER_XY_COLOR_MODE,
    CONF_DEFAULT_LIGHT_TRANSITION,
    CONF_ENABLE_ENHANCED_LIGHT_TRANSITION,
    CONF_ENABLE_LIGHT_TRANSITIONING_FLAG,
    DATA_ZHA,
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

DEFAULT_ON_OFF_TRANSITION = 1  # most bulbs default to a 1-second turn on/off transition
DEFAULT_EXTRA_TRANSITION_DELAY_SHORT = 0.25
DEFAULT_EXTRA_TRANSITION_DELAY_LONG = 2.0
DEFAULT_LONG_TRANSITION_TIME = 10
DEFAULT_MIN_BRIGHTNESS = 2

FLASH_EFFECTS = {
    light.FLASH_SHORT: Identify.EffectIdentifier.Blink,
    light.FLASH_LONG: Identify.EffectIdentifier.Breathe,
}

STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, Platform.LIGHT)
GROUP_MATCH = functools.partial(ZHA_ENTITIES.group_match, Platform.LIGHT)
PARALLEL_UPDATES = 0
SIGNAL_LIGHT_GROUP_STATE_CHANGED = "zha_light_group_state_changed"
SIGNAL_LIGHT_GROUP_TRANSITION_START = "zha_light_group_transition_start"
SIGNAL_LIGHT_GROUP_TRANSITION_FINISHED = "zha_light_group_transition_finished"
DEFAULT_MIN_TRANSITION_MANUFACTURERS = {"sengled"}

COLOR_MODES_GROUP_LIGHT = {ColorMode.COLOR_TEMP, ColorMode.XY}
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
        self._zha_device: ZHADevice = None
        super().__init__(*args, **kwargs)
        self._attr_min_mireds: int | None = 153
        self._attr_max_mireds: int | None = 500
        self._attr_color_mode = ColorMode.UNKNOWN  # Set by sub classes
        self._attr_supported_features: int = 0
        self._attr_state: bool | None
        self._off_with_transition: bool = False
        self._off_brightness: int | None = None
        self._zha_config_transition = self._DEFAULT_MIN_TRANSITION_TIME
        self._zha_config_enhanced_light_transition: bool = False
        self._zha_config_enable_light_transitioning_flag: bool = True
        self._zha_config_always_prefer_xy_color_mode: bool = True
        self._on_off_channel = None
        self._level_channel = None
        self._color_channel = None
        self._identify_channel = None
        self._transitioning: bool = False
        self._transition_listener: Callable[[], None] | None = None

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
        if self._attr_state is None:
            return False
        return self._attr_state

    @callback
    def set_level(self, value: int) -> None:
        """Set the brightness of this light between 0..254.

        brightness level 255 is a special value instructing the device to come
        on at `on_level` Zigbee attribute value, regardless of the last set
        level
        """
        if self._transitioning:
            self.debug(
                "received level %s while transitioning - skipping update",
                value,
            )
            return
        value = max(0, min(254, value))
        self._attr_brightness = value
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
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
        xy_color = kwargs.get(light.ATTR_XY_COLOR)
        hs_color = kwargs.get(light.ATTR_HS_COLOR)

        set_transition_flag = (
            brightness_supported(self._attr_supported_color_modes)
            or temperature is not None
            or xy_color is not None
            or hs_color is not None
        ) and self._zha_config_enable_light_transitioning_flag
        transition_time = (
            (
                duration / 10 + DEFAULT_EXTRA_TRANSITION_DELAY_SHORT
                if (
                    (brightness is not None or transition is not None)
                    and brightness_supported(self._attr_supported_color_modes)
                    or (self._off_with_transition and self._off_brightness is not None)
                    or temperature is not None
                    or xy_color is not None
                    or hs_color is not None
                )
                else DEFAULT_ON_OFF_TRANSITION + DEFAULT_EXTRA_TRANSITION_DELAY_SHORT
            )
            if set_transition_flag
            else 0
        )

        # If we need to pause attribute report parsing, we'll do so here.
        # After successful calls, we later start a timer to unset the flag after transition_time.
        # On an error on the first move to level call, we unset the flag immediately if no previous timer is running.
        # On an error on subsequent calls, we start the transition timer, as a brightness call might have come through.
        if set_transition_flag:
            self.async_transition_set_flag()

        # If the light is currently off but a turn_on call with a color/temperature is sent,
        # the light needs to be turned on first at a low brightness level where the light is immediately transitioned
        # to the correct color. Afterwards, the transition is only from the low brightness to the new brightness.
        # Otherwise, the transition is from the color the light had before being turned on to the new color.
        # This can look especially bad with transitions longer than a second. We do not want to do this for
        # devices that need to be forced to use the on command because we would end up with 4 commands sent:
        # move to level, on, color, move to level... We also will not set this if the bulb is already in the
        # desired color mode with the desired color or color temperature.
        new_color_provided_while_off = (
            self._zha_config_enhanced_light_transition
            and not self._FORCE_ON
            and not self._attr_state
            and (
                (
                    temperature is not None
                    and (
                        self._attr_color_temp != temperature
                        or self._attr_color_mode != ColorMode.COLOR_TEMP
                    )
                )
                or (
                    xy_color is not None
                    and (
                        self._attr_xy_color != xy_color
                        or self._attr_color_mode != ColorMode.XY
                    )
                )
                or (
                    hs_color is not None
                    and (
                        self._attr_hs_color != hs_color
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
            level = self._attr_brightness or 254

        t_log = {}

        if new_color_provided_while_off:
            # If the light is currently off, we first need to turn it on at a low brightness level with no transition.
            # After that, we set it to the desired color/temperature with no transition.
            result = await self._level_channel.move_to_level_with_on_off(
                level=DEFAULT_MIN_BRIGHTNESS,
                transition_time=self._DEFAULT_MIN_TRANSITION_TIME,
            )
            t_log["move_to_level_with_on_off"] = result
            if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
                # First 'move to level' call failed, so if the transitioning delay isn't running from a previous call,
                # the flag can be unset immediately
                if set_transition_flag and not self._transition_listener:
                    self.async_transition_complete()
                self.debug("turned on: %s", t_log)
                return
            # Currently only setting it to "on", as the correct level state will be set at the second move_to_level call
            self._attr_state = True

        if (
            (brightness is not None or transition)
            and not new_color_provided_while_off
            and brightness_supported(self._attr_supported_color_modes)
        ):
            result = await self._level_channel.move_to_level_with_on_off(
                level=level,
                transition_time=duration,
            )
            t_log["move_to_level_with_on_off"] = result
            if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
                # First 'move to level' call failed, so if the transitioning delay isn't running from a previous call,
                # the flag can be unset immediately
                if set_transition_flag and not self._transition_listener:
                    self.async_transition_complete()
                self.debug("turned on: %s", t_log)
                return
            self._attr_state = bool(level)
            if level:
                self._attr_brightness = level

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
                # 'On' call failed, but as brightness may still transition (for FORCE_ON lights),
                # we start the timer to unset the flag after the transition_time if necessary.
                self.async_transition_start_timer(transition_time)
                self.debug("turned on: %s", t_log)
                return
            self._attr_state = True

        if not await self.async_handle_color_commands(
            temperature,
            duration,
            hs_color,
            xy_color,
            new_color_provided_while_off,
            t_log,
        ):
            # Color calls failed, but as brightness may still transition, we start the timer to unset the flag
            self.async_transition_start_timer(transition_time)
            self.debug("turned on: %s", t_log)
            return

        if new_color_provided_while_off:
            # The light is has the correct color, so we can now transition it to the correct brightness level.
            result = await self._level_channel.move_to_level(
                level=level, transition_time=duration
            )
            t_log["move_to_level_if_color"] = result
            if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
                self.debug("turned on: %s", t_log)
                return
            self._attr_state = bool(level)
            if level:
                self._attr_brightness = level

        # Our light is guaranteed to have just started the transitioning process if necessary,
        # so we start the delay for the transition (to stop parsing attribute reports after the completed transition).
        self.async_transition_start_timer(transition_time)

        if effect == light.EFFECT_COLORLOOP:
            result = await self._color_channel.color_loop_set(
                update_flags=(
                    Color.ColorLoopUpdateFlags.Action
                    | Color.ColorLoopUpdateFlags.Direction
                    | Color.ColorLoopUpdateFlags.Time
                ),
                action=Color.ColorLoopAction.Activate_from_current_hue,
                direction=Color.ColorLoopDirection.Increment,
                time=transition if transition else 7,
                start_hue=0,
            )
            t_log["color_loop_set"] = result
            self._attr_effect = light.EFFECT_COLORLOOP
        elif (
            self._attr_effect == light.EFFECT_COLORLOOP
            and effect != light.EFFECT_COLORLOOP
        ):
            result = await self._color_channel.color_loop_set(
                update_flags=Color.ColorLoopUpdateFlags.Action,
                action=Color.ColorLoopAction.Deactivate,
                direction=Color.ColorLoopDirection.Decrement,
                time=0,
                start_hue=0,
            )
            t_log["color_loop_set"] = result
            self._attr_effect = None

        if flash is not None:
            result = await self._identify_channel.trigger_effect(
                effect_id=FLASH_EFFECTS[flash],
                effect_variant=Identify.EffectVariant.Default,
            )
            t_log["trigger_effect"] = result

        self._off_with_transition = False
        self._off_brightness = None
        self.debug("turned on: %s", t_log)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        transition = kwargs.get(light.ATTR_TRANSITION)
        supports_level = brightness_supported(self._attr_supported_color_modes)

        transition_time = (
            transition or self._DEFAULT_MIN_TRANSITION_TIME
            if transition is not None
            else DEFAULT_ON_OFF_TRANSITION
        ) + DEFAULT_EXTRA_TRANSITION_DELAY_SHORT

        # Start pausing attribute report parsing
        if self._zha_config_enable_light_transitioning_flag:
            self.async_transition_set_flag()

        # is not none looks odd here but it will override built in bulb transition times if we pass 0 in here
        if transition is not None and supports_level:
            result = await self._level_channel.move_to_level_with_on_off(
                level=0,
                transition_time=(transition * 10 or self._DEFAULT_MIN_TRANSITION_TIME),
            )
        else:
            result = await self._on_off_channel.off()

        # Pause parsing attribute reports until transition is complete
        if self._zha_config_enable_light_transitioning_flag:
            self.async_transition_start_timer(transition_time)
        self.debug("turned off: %s", result)
        if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
            return
        self._attr_state = False

        if supports_level:
            # store current brightness so that the next turn_on uses it.
            self._off_with_transition = transition is not None
            self._off_brightness = self._attr_brightness

        self.async_write_ha_state()

    async def async_handle_color_commands(
        self,
        temperature,
        duration,
        hs_color,
        xy_color,
        new_color_provided_while_off,
        t_log,
    ):
        """Process ZCL color commands."""

        transition_time = (
            self._DEFAULT_MIN_TRANSITION_TIME
            if new_color_provided_while_off
            else duration
        )

        if temperature is not None:
            result = await self._color_channel.move_to_color_temp(
                color_temp_mireds=temperature,
                transition_time=transition_time,
            )
            t_log["move_to_color_temp"] = result
            if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
                return False
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_color_temp = temperature
            self._attr_xy_color = None
            self._attr_hs_color = None

        if hs_color is not None:
            if (
                not isinstance(self, LightGroup)
                and self._color_channel.enhanced_hue_supported
            ):
                result = await self._color_channel.enhanced_move_to_hue_and_saturation(
                    enhanced_hue=int(hs_color[0] * 65535 / 360),
                    saturation=int(hs_color[1] * 2.54),
                    transition_time=transition_time,
                )
                t_log["enhanced_move_to_hue_and_saturation"] = result
            else:
                result = await self._color_channel.move_to_hue_and_saturation(
                    hue=int(hs_color[0] * 254 / 360),
                    saturation=int(hs_color[1] * 2.54),
                    transition_time=transition_time,
                )
                t_log["move_to_hue_and_saturation"] = result
            if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
                return False
            self._attr_color_mode = ColorMode.HS
            self._attr_hs_color = hs_color
            self._attr_xy_color = None
            self._attr_color_temp = None
            xy_color = None  # don't set xy_color if it is also present

        if xy_color is not None:
            result = await self._color_channel.move_to_color(
                color_x=int(xy_color[0] * 65535),
                color_y=int(xy_color[1] * 65535),
                transition_time=transition_time,
            )
            t_log["move_to_color"] = result
            if isinstance(result, Exception) or result[1] is not Status.SUCCESS:
                return False
            self._attr_color_mode = ColorMode.XY
            self._attr_xy_color = xy_color
            self._attr_color_temp = None
            self._attr_hs_color = None

        return True

    @callback
    def async_transition_set_flag(self) -> None:
        """Set _transitioning to True."""
        self.debug("setting transitioning flag to True")
        self._transitioning = True
        if isinstance(self, LightGroup):
            async_dispatcher_send(
                self.hass,
                SIGNAL_LIGHT_GROUP_TRANSITION_START,
                {"entity_ids": self._entity_ids},
            )
        if self._transition_listener is not None:
            self._transition_listener()

    @callback
    def async_transition_start_timer(self, transition_time) -> None:
        """Start a timer to unset _transitioning after transition_time if necessary."""
        if not transition_time:
            return
        # For longer transitions, we want to extend the timer a bit more
        if transition_time >= DEFAULT_LONG_TRANSITION_TIME:
            transition_time += DEFAULT_EXTRA_TRANSITION_DELAY_LONG
        self.debug("starting transitioning timer for %s", transition_time)
        self._transition_listener = async_call_later(
            self._zha_device.hass,
            transition_time,
            self.async_transition_complete,
        )

    @callback
    def async_transition_complete(self, _=None) -> None:
        """Set _transitioning to False and write HA state."""
        self.debug("transition complete - future attribute reports will write HA state")
        self._transitioning = False
        if self._transition_listener:
            self._transition_listener()
            self._transition_listener = None
        self.async_write_ha_state()
        if isinstance(self, LightGroup):
            async_dispatcher_send(
                self.hass,
                SIGNAL_LIGHT_GROUP_TRANSITION_FINISHED,
                {"entity_ids": self._entity_ids},
            )
            if self._debounced_member_refresh is not None:
                self.debug("transition complete - refreshing group member states")
                asyncio.create_task(self._debounced_member_refresh.async_call())


@STRICT_MATCH(channel_names=CHANNEL_ON_OFF, aux_channels={CHANNEL_COLOR, CHANNEL_LEVEL})
class Light(BaseLight, ZhaEntity):
    """Representation of a ZHA or ZLL light."""

    _attr_supported_color_modes: set[ColorMode]
    _REFRESH_INTERVAL = (45, 75)

    def __init__(self, unique_id, zha_device: ZHADevice, channels, **kwargs):
        """Initialize the ZHA light."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._on_off_channel = self.cluster_channels[CHANNEL_ON_OFF]
        self._attr_state = bool(self._on_off_channel.on_off)
        self._level_channel = self.cluster_channels.get(CHANNEL_LEVEL)
        self._color_channel = self.cluster_channels.get(CHANNEL_COLOR)
        self._identify_channel = self.zha_device.channels.identify_ch
        if self._color_channel:
            self._attr_min_mireds: int = self._color_channel.min_mireds
            self._attr_max_mireds: int = self._color_channel.max_mireds
        self._cancel_refresh_handle: CALLBACK_TYPE | None = None
        effect_list = []

        self._zha_config_always_prefer_xy_color_mode = async_get_zha_config_value(
            zha_device.gateway.config_entry,
            ZHA_OPTIONS,
            CONF_ALWAYS_PREFER_XY_COLOR_MODE,
            True,
        )

        self._attr_supported_color_modes = {ColorMode.ONOFF}
        if self._level_channel:
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
            self._attr_supported_features |= light.LightEntityFeature.TRANSITION
            self._attr_brightness = self._level_channel.current_level

        if self._color_channel:
            if self._color_channel.color_temp_supported:
                self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
                self._attr_color_temp = self._color_channel.color_temperature

            if self._color_channel.xy_supported and (
                self._zha_config_always_prefer_xy_color_mode
                or not self._color_channel.hs_supported
            ):
                self._attr_supported_color_modes.add(ColorMode.XY)
                curr_x = self._color_channel.current_x
                curr_y = self._color_channel.current_y
                if curr_x is not None and curr_y is not None:
                    self._attr_xy_color = (curr_x / 65535, curr_y / 65535)
                else:
                    self._attr_xy_color = (0, 0)

            if (
                self._color_channel.hs_supported
                and not self._zha_config_always_prefer_xy_color_mode
            ):
                self._attr_supported_color_modes.add(ColorMode.HS)
                if (
                    self._color_channel.enhanced_hue_supported
                    and self._color_channel.enhanced_current_hue is not None
                ):
                    curr_hue = self._color_channel.enhanced_current_hue * 65535 / 360
                elif self._color_channel.current_hue is not None:
                    curr_hue = self._color_channel.current_hue * 254 / 360
                else:
                    curr_hue = 0

                if (curr_saturation := self._color_channel.current_saturation) is None:
                    curr_saturation = 0

                self._attr_hs_color = (
                    int(curr_hue),
                    int(curr_saturation * 2.54),
                )

            if self._color_channel.color_loop_supported:
                self._attr_supported_features |= light.LightEntityFeature.EFFECT
                effect_list.append(light.EFFECT_COLORLOOP)
                if self._color_channel.color_loop_active == 1:
                    self._attr_effect = light.EFFECT_COLORLOOP
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
                self._attr_color_mode = ColorMode.XY

        if self._identify_channel:
            self._attr_supported_features |= light.LightEntityFeature.FLASH

        if effect_list:
            self._attr_effect_list = effect_list

        self._zha_config_transition = async_get_zha_config_value(
            zha_device.gateway.config_entry,
            ZHA_OPTIONS,
            CONF_DEFAULT_LIGHT_TRANSITION,
            0,
        )
        self._zha_config_enhanced_light_transition = async_get_zha_config_value(
            zha_device.gateway.config_entry,
            ZHA_OPTIONS,
            CONF_ENABLE_ENHANCED_LIGHT_TRANSITION,
            False,
        )
        self._zha_config_enable_light_transitioning_flag = async_get_zha_config_value(
            zha_device.gateway.config_entry,
            ZHA_OPTIONS,
            CONF_ENABLE_LIGHT_TRANSITIONING_FLAG,
            True,
        )

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Set the state."""
        if self._transitioning:
            self.debug(
                "received onoff %s while transitioning - skipping update",
                value,
            )
            return
        self._attr_state = bool(value)
        if value:
            self._off_with_transition = False
            self._off_brightness = None
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
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

        @callback
        def transition_on(signal):
            """Handle a transition start event from a group."""
            if self.entity_id in signal["entity_ids"]:
                self.debug(
                    "group transition started - setting member transitioning flag"
                )
                self._transitioning = True

        self.async_accept_signal(
            None,
            SIGNAL_LIGHT_GROUP_TRANSITION_START,
            transition_on,
            signal_override=True,
        )

        @callback
        def transition_off(signal):
            """Handle a transition finished event from a group."""
            if self.entity_id in signal["entity_ids"]:
                self.debug(
                    "group transition completed - unsetting member transitioning flag"
                )
                self._transitioning = False

        self.async_accept_signal(
            None,
            SIGNAL_LIGHT_GROUP_TRANSITION_FINISHED,
            transition_off,
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
        self._attr_state = last_state.state == STATE_ON
        if "brightness" in last_state.attributes:
            self._attr_brightness = last_state.attributes["brightness"]
        if "off_with_transition" in last_state.attributes:
            self._off_with_transition = last_state.attributes["off_with_transition"]
        if "off_brightness" in last_state.attributes:
            self._off_brightness = last_state.attributes["off_brightness"]
        if "color_mode" in last_state.attributes:
            self._attr_color_mode = ColorMode(last_state.attributes["color_mode"])
        if "color_temp" in last_state.attributes:
            self._attr_color_temp = last_state.attributes["color_temp"]
        if "xy_color" in last_state.attributes:
            self._attr_xy_color = last_state.attributes["xy_color"]
        if "hs_color" in last_state.attributes:
            self._attr_hs_color = last_state.attributes["hs_color"]
        if "effect" in last_state.attributes:
            self._attr_effect = last_state.attributes["effect"]

    async def async_get_state(self) -> None:
        """Attempt to retrieve the state from the light."""
        if not self._attr_available:
            return
        self.debug("polling current state")
        if self._on_off_channel:
            state = await self._on_off_channel.get_attribute_value(
                "on_off", from_cache=False
            )
            if state is not None:
                self._attr_state = state
        if self._level_channel:
            level = await self._level_channel.get_attribute_value(
                "current_level", from_cache=False
            )
            if level is not None:
                self._attr_brightness = level
        if self._color_channel:
            attributes = [
                "color_mode",
                "current_x",
                "current_y",
            ]
            if (
                not self._zha_config_always_prefer_xy_color_mode
                and self._color_channel.enhanced_hue_supported
            ):
                attributes.append("enhanced_current_hue")
                attributes.append("current_saturation")
            if (
                self._color_channel.hs_supported
                and not self._color_channel.enhanced_hue_supported
                and not self._zha_config_always_prefer_xy_color_mode
            ):
                attributes.append("current_hue")
                attributes.append("current_saturation")
            if self._color_channel.color_temp_supported:
                attributes.append("color_temperature")
            if self._color_channel.color_loop_supported:
                attributes.append("color_loop_active")

            results = await self._color_channel.get_attributes(
                attributes, from_cache=False, only_cache=False
            )

            if (color_mode := results.get("color_mode")) is not None:
                if color_mode == Color.ColorMode.Color_temperature:
                    self._attr_color_mode = ColorMode.COLOR_TEMP
                    color_temp = results.get("color_temperature")
                    if color_temp is not None and color_mode:
                        self._attr_color_temp = color_temp
                        self._attr_xy_color = None
                        self._attr_hs_color = None
                elif (
                    color_mode == Color.ColorMode.Hue_and_saturation
                    and not self._zha_config_always_prefer_xy_color_mode
                ):
                    self._attr_color_mode = ColorMode.HS
                    if self._color_channel.enhanced_hue_supported:
                        current_hue = results.get("enhanced_current_hue")
                    else:
                        current_hue = results.get("current_hue")
                    current_saturation = results.get("current_saturation")
                    if current_hue is not None and current_saturation is not None:
                        self._attr_hs_color = (
                            int(current_hue * 360 / 65535)
                            if self._color_channel.enhanced_hue_supported
                            else int(current_hue * 360 / 254),
                            int(current_saturation / 2.54),
                        )
                        self._attr_xy_color = None
                        self._attr_color_temp = None
                else:
                    self._attr_color_mode = ColorMode.XY
                    color_x = results.get("current_x")
                    color_y = results.get("current_y")
                    if color_x is not None and color_y is not None:
                        self._attr_xy_color = (color_x / 65535, color_y / 65535)
                        self._attr_color_temp = None
                        self._attr_hs_color = None

            color_loop_active = results.get("color_loop_active")
            if color_loop_active is not None:
                if color_loop_active == 1:
                    self._attr_effect = light.EFFECT_COLORLOOP
                else:
                    self._attr_effect = None

    async def async_update(self) -> None:
        """Update to the latest state."""
        if self._transitioning:
            self.debug("skipping async_update while transitioning")
            return
        await self.async_get_state()

    async def _refresh(self, time):
        """Call async_get_state at an interval."""
        if self._transitioning:
            self.debug("skipping _refresh while transitioning")
            return
        await self.async_get_state()
        self.async_write_ha_state()

    async def _maybe_force_refresh(self, signal):
        """Force update the state if the signal contains the entity id for this entity."""
        if self.entity_id in signal["entity_ids"]:
            if self._transitioning:
                self.debug("skipping _maybe_force_refresh while transitioning")
                return
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
    manufacturers=DEFAULT_MIN_TRANSITION_MANUFACTURERS,
)
class MinTransitionLight(Light):
    """Representation of a light which does not react to any "move to" calls with 0 as a transition."""

    _DEFAULT_MIN_TRANSITION_TIME = 1


@GROUP_MATCH()
class LightGroup(BaseLight, ZhaGroupEntity):
    """Representation of a light group."""

    def __init__(
        self,
        entity_ids: list[str],
        unique_id: str,
        group_id: int,
        zha_device: ZHADevice,
        **kwargs: Any,
    ) -> None:
        """Initialize a light group."""
        super().__init__(entity_ids, unique_id, group_id, zha_device, **kwargs)
        group = self.zha_device.gateway.get_group(self._group_id)
        self._DEFAULT_MIN_TRANSITION_TIME = any(  # pylint: disable=invalid-name
            member.device.manufacturer in DEFAULT_MIN_TRANSITION_MANUFACTURERS
            for member in group.members
        )
        self._on_off_channel = group.endpoint[OnOff.cluster_id]
        self._level_channel = group.endpoint[LevelControl.cluster_id]
        self._color_channel = group.endpoint[Color.cluster_id]
        self._identify_channel = group.endpoint[Identify.cluster_id]
        self._debounced_member_refresh: Debouncer | None = None
        self._zha_config_transition = async_get_zha_config_value(
            zha_device.gateway.config_entry,
            ZHA_OPTIONS,
            CONF_DEFAULT_LIGHT_TRANSITION,
            0,
        )
        self._zha_config_enable_light_transitioning_flag = async_get_zha_config_value(
            zha_device.gateway.config_entry,
            ZHA_OPTIONS,
            CONF_ENABLE_LIGHT_TRANSITIONING_FLAG,
            True,
        )
        self._zha_config_always_prefer_xy_color_mode = async_get_zha_config_value(
            zha_device.gateway.config_entry,
            ZHA_OPTIONS,
            CONF_ALWAYS_PREFER_XY_COLOR_MODE,
            True,
        )
        self._zha_config_enhanced_light_transition = False
        self._attr_color_mode = None

    # remove this when all ZHA platforms and base entities are updated
    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self._attr_available

    async def async_added_to_hass(self) -> None:
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await super().async_turn_on(**kwargs)
        if self._transitioning:
            return
        if self._debounced_member_refresh:
            await self._debounced_member_refresh.async_call()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await super().async_turn_off(**kwargs)
        if self._transitioning:
            return
        if self._debounced_member_refresh:
            await self._debounced_member_refresh.async_call()

    @callback
    def async_state_changed_listener(self, event: Event) -> None:
        """Handle child updates."""
        if self._transitioning:
            self.debug("skipping group entity state update during transition")
            return
        super().async_state_changed_listener(event)

    async def async_update_ha_state(self, force_refresh: bool = False) -> None:
        """Update Home Assistant with current state of entity."""
        if self._transitioning:
            self.debug("skipping group entity state update during transition")
            return
        await super().async_update_ha_state(force_refresh)

    async def async_update(self) -> None:
        """Query all members and determine the light group state."""
        all_states = [self.hass.states.get(x) for x in self._entity_ids]
        states: list[State] = list(filter(None, all_states))
        on_states = [state for state in states if state.state == STATE_ON]

        self._attr_state = len(on_states) > 0
        self._attr_available = any(state.state != STATE_UNAVAILABLE for state in states)

        self._attr_brightness = helpers.reduce_attribute(
            on_states, light.ATTR_BRIGHTNESS
        )

        self._attr_xy_color = helpers.reduce_attribute(
            on_states, light.ATTR_XY_COLOR, reduce=helpers.mean_tuple
        )

        if not self._zha_config_always_prefer_xy_color_mode:
            self._attr_hs_color = helpers.reduce_attribute(
                on_states, light.ATTR_HS_COLOR, reduce=helpers.mean_tuple
            )

        self._attr_color_temp = helpers.reduce_attribute(
            on_states, light.ATTR_COLOR_TEMP
        )
        self._attr_min_mireds = helpers.reduce_attribute(
            states, light.ATTR_MIN_MIREDS, default=153, reduce=min
        )
        self._attr_max_mireds = helpers.reduce_attribute(
            states, light.ATTR_MAX_MIREDS, default=500, reduce=max
        )

        self._attr_effect_list = None
        all_effect_lists = list(
            helpers.find_state_attributes(states, light.ATTR_EFFECT_LIST)
        )
        if all_effect_lists:
            # Merge all effects from all effect_lists with a union merge.
            self._attr_effect_list = list(set().union(*all_effect_lists))

        self._attr_effect = None
        all_effects = list(helpers.find_state_attributes(on_states, light.ATTR_EFFECT))
        if all_effects:
            # Report the most common effect.
            effects_count = Counter(itertools.chain(all_effects))
            self._attr_effect = effects_count.most_common(1)[0][0]

        self._attr_color_mode = None
        all_color_modes = list(
            helpers.find_state_attributes(on_states, light.ATTR_COLOR_MODE)
        )
        if all_color_modes:
            # Report the most common color mode, select brightness and onoff last
            color_mode_count = Counter(itertools.chain(all_color_modes))
            if ColorMode.ONOFF in color_mode_count:
                color_mode_count[ColorMode.ONOFF] = -1
            if ColorMode.BRIGHTNESS in color_mode_count:
                color_mode_count[ColorMode.BRIGHTNESS] = 0
            self._attr_color_mode = color_mode_count.most_common(1)[0][0]
            if self._attr_color_mode == ColorMode.HS and (
                color_mode_count[ColorMode.HS] != len(self._group.members)
                or self._zha_config_always_prefer_xy_color_mode
            ):  # switch to XY if all members do not support HS
                self._attr_color_mode = ColorMode.XY

        self._attr_supported_color_modes = None
        all_supported_color_modes = list(
            helpers.find_state_attributes(states, light.ATTR_SUPPORTED_COLOR_MODES)
        )
        if all_supported_color_modes:
            # Merge all color modes.
            self._attr_supported_color_modes = cast(
                set[str], set().union(*all_supported_color_modes)
            )

        self._attr_supported_features = LightEntityFeature(0)
        for support in helpers.find_state_attributes(states, ATTR_SUPPORTED_FEATURES):
            # Merge supported features by emulating support for every feature
            # we find.
            self._attr_supported_features |= support
        # Bitwise-and the supported features with the GroupedLight's features
        # so that we don't break in the future when a new feature is added.
        self._attr_supported_features &= SUPPORT_GROUP_LIGHT

    async def _force_member_updates(self) -> None:
        """Force the update of member entities to ensure the states are correct for bulbs that don't report their state."""
        async_dispatcher_send(
            self.hass,
            SIGNAL_LIGHT_GROUP_STATE_CHANGED,
            {"entity_ids": self._entity_ids},
        )
