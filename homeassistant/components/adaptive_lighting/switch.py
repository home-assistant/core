"""Switch for the Adaptive Lighting integration."""
from __future__ import annotations

import asyncio
import bisect
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
import datetime
from datetime import timedelta
import functools
import hashlib
import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import astral
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_BRIGHTNESS_STEP,
    ATTR_BRIGHTNESS_STEP_PCT,
    ATTR_COLOR_NAME,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE_VALUE,
    ATTR_XY_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_TRANSITION,
    SUPPORT_WHITE_VALUE,
    VALID_TRANSITION,
    is_on,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_SERVICE,
    ATTR_SERVICE_DATA,
    ATTR_SUPPORTED_FEATURES,
    CONF_NAME,
    EVENT_CALL_SERVICE,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_STATE_CHANGED,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import (
    Context,
    Event,
    HomeAssistant,
    ServiceCall,
    State,
    callback,
)
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.sun import get_astral_location
from homeassistant.util import slugify
from homeassistant.util.color import (
    color_RGB_to_xy,
    color_temperature_kelvin_to_mired,
    color_temperature_to_rgb,
    color_xy_to_hs,
)
import homeassistant.util.dt as dt_util

from .const import (
    ADAPT_BRIGHTNESS_SWITCH,
    ADAPT_COLOR_SWITCH,
    ATTR_ADAPT_BRIGHTNESS,
    ATTR_ADAPT_COLOR,
    ATTR_TURN_ON_OFF_LISTENER,
    CONF_DETECT_NON_HA_CHANGES,
    CONF_INITIAL_TRANSITION,
    CONF_INTERVAL,
    CONF_LIGHTS,
    CONF_MANUAL_CONTROL,
    CONF_MAX_BRIGHTNESS,
    CONF_MAX_COLOR_TEMP,
    CONF_MIN_BRIGHTNESS,
    CONF_MIN_COLOR_TEMP,
    CONF_ONLY_ONCE,
    CONF_PREFER_RGB_COLOR,
    CONF_SEPARATE_TURN_ON_COMMANDS,
    CONF_SLEEP_BRIGHTNESS,
    CONF_SLEEP_COLOR_TEMP,
    CONF_SUNRISE_OFFSET,
    CONF_SUNRISE_TIME,
    CONF_SUNSET_OFFSET,
    CONF_SUNSET_TIME,
    CONF_TAKE_OVER_CONTROL,
    CONF_TRANSITION,
    CONF_TURN_ON_LIGHTS,
    DOMAIN,
    EXTRA_VALIDATION,
    ICON,
    SERVICE_APPLY,
    SERVICE_SET_MANUAL_CONTROL,
    SLEEP_MODE_SWITCH,
    SUN_EVENT_MIDNIGHT,
    SUN_EVENT_NOON,
    TURNING_OFF_DELAY,
    VALIDATION_TUPLES,
    replace_none_str,
)

_SUPPORT_OPTS = {
    "brightness": SUPPORT_BRIGHTNESS,
    "white_value": SUPPORT_WHITE_VALUE,
    "color_temp": SUPPORT_COLOR_TEMP,
    "color": SUPPORT_COLOR,
    "transition": SUPPORT_TRANSITION,
}

_ORDER = (SUN_EVENT_SUNRISE, SUN_EVENT_NOON, SUN_EVENT_SUNSET, SUN_EVENT_MIDNIGHT)
_ALLOWED_ORDERS = {_ORDER[i:] + _ORDER[:i] for i in range(len(_ORDER))}

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

# Consider it a significant change when attribute changes more than
BRIGHTNESS_CHANGE = 25  # ≈10% of total range
COLOR_TEMP_CHANGE = 20  # ≈5% of total range
RGB_REDMEAN_CHANGE = 80  # ≈10% of total range

COLOR_ATTRS = {  # Should ATTR_PROFILE be in here?
    ATTR_COLOR_NAME,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_XY_COLOR,
}

BRIGHTNESS_ATTRS = {
    ATTR_BRIGHTNESS,
    ATTR_WHITE_VALUE,
    ATTR_BRIGHTNESS_PCT,
    ATTR_BRIGHTNESS_STEP,
    ATTR_BRIGHTNESS_STEP_PCT,
}

# Keep a short domain version for the context instances (which can only be 36 chars)
_DOMAIN_SHORT = "adapt_lgt"


def _short_hash(string: str, length: int = 4) -> str:
    """Create a hash of 'string' with length 'length'."""
    return hashlib.sha1(string.encode("UTF-8")).hexdigest()[:length]


def create_context(name: str, which: str, index: int) -> Context:
    """Create a context that can identify this integration."""
    # Use a hash for the name because otherwise the context might become
    # too long (max len == 36) to fit in the database.
    name_hash = _short_hash(name)
    return Context(id=f"{_DOMAIN_SHORT}_{name_hash}_{which}_{index}")


def is_our_context(context: Optional[Context]) -> bool:
    """Check whether this integration created 'context'."""
    if context is None:
        return False
    return context.id.startswith(_DOMAIN_SHORT)


def _split_service_data(service_data, adapt_brightness, adapt_color):
    """Split service_data into two dictionaries (for color and brightness)."""
    transition = service_data.get(ATTR_TRANSITION)
    if transition is not None:
        # Split the transition over both commands
        service_data[ATTR_TRANSITION] /= 2
    service_datas = []
    if adapt_color:
        service_data_color = service_data.copy()
        service_data_color.pop(ATTR_WHITE_VALUE, None)
        service_data_color.pop(ATTR_BRIGHTNESS, None)
        service_datas.append(service_data_color)
    if adapt_brightness:
        service_data_brightness = service_data.copy()
        service_data_brightness.pop(ATTR_RGB_COLOR, None)
        service_data_brightness.pop(ATTR_COLOR_TEMP, None)
        service_datas.append(service_data_brightness)
    return service_datas


async def handle_apply(switch: AdaptiveSwitch, service_call: ServiceCall):
    """Handle the entity service apply."""
    hass = switch.hass
    data = service_call.data
    all_lights = _expand_light_groups(hass, data[CONF_LIGHTS])
    switch.turn_on_off_listener.lights.update(all_lights)

    for light in all_lights:
        if data[CONF_TURN_ON_LIGHTS] or is_on(hass, light):
            await switch._adapt_light(  # pylint: disable=protected-access
                light,
                data[CONF_TRANSITION],
                data[ATTR_ADAPT_BRIGHTNESS],
                data[ATTR_ADAPT_COLOR],
                data[CONF_PREFER_RGB_COLOR],
                force=True,
            )


async def handle_set_manual_control(switch: AdaptiveSwitch, service_call: ServiceCall):
    """Set or unset lights as 'manually controlled'."""
    lights = service_call.data[CONF_LIGHTS]
    if not lights:
        all_lights = switch._lights  # pylint: disable=protected-access
    else:
        all_lights = _expand_light_groups(switch.hass, lights)
    _LOGGER.debug(
        "Called 'adaptive_lighting.set_manual_control' service with '%s'",
        service_call.data,
    )
    if service_call.data[CONF_MANUAL_CONTROL]:
        for light in all_lights:
            switch.turn_on_off_listener.manual_control[light] = True
            _fire_manual_control_event(switch, light, service_call.context)
    else:
        switch.turn_on_off_listener.reset(*all_lights)
        # pylint: disable=protected-access
        if switch.is_on:
            await switch._update_attrs_and_maybe_adapt_lights(
                all_lights,
                transition=switch._initial_transition,
                force=True,
                context=switch.create_context("service"),
            )


@callback
def _fire_manual_control_event(
    switch: AdaptiveSwitch, light: str, context: Context, is_async=True
):
    """Fire an event that 'light' is marked as manual_control."""
    hass = switch.hass
    fire = hass.bus.async_fire if is_async else hass.bus.fire
    _LOGGER.debug(
        "'adaptive_lighting.manual_control' event fired for %s for light %s",
        switch.entity_id,
        light,
    )
    fire(
        f"{DOMAIN}.manual_control",
        {ATTR_ENTITY_ID: light, SWITCH_DOMAIN: switch.entity_id},
        context=context,
    )


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: bool
):
    """Set up the AdaptiveLighting switch."""
    data = hass.data[DOMAIN]
    assert config_entry.entry_id in data

    if ATTR_TURN_ON_OFF_LISTENER not in data:
        data[ATTR_TURN_ON_OFF_LISTENER] = TurnOnOffListener(hass)
    turn_on_off_listener = data[ATTR_TURN_ON_OFF_LISTENER]

    sleep_mode_switch = SimpleSwitch("Sleep Mode", False, hass, config_entry)
    adapt_color_switch = SimpleSwitch("Adapt Color", True, hass, config_entry)
    adapt_brightness_switch = SimpleSwitch("Adapt Brightness", True, hass, config_entry)
    switch = AdaptiveSwitch(
        hass,
        config_entry,
        turn_on_off_listener,
        sleep_mode_switch,
        adapt_color_switch,
        adapt_brightness_switch,
    )

    data[config_entry.entry_id][SLEEP_MODE_SWITCH] = sleep_mode_switch
    data[config_entry.entry_id][ADAPT_COLOR_SWITCH] = adapt_color_switch
    data[config_entry.entry_id][ADAPT_BRIGHTNESS_SWITCH] = adapt_brightness_switch
    data[config_entry.entry_id][SWITCH_DOMAIN] = switch

    async_add_entities(
        [switch, sleep_mode_switch, adapt_color_switch, adapt_brightness_switch],
        update_before_add=True,
    )

    # Register `apply` service
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        SERVICE_APPLY,
        {
            vol.Required(CONF_LIGHTS): cv.entity_ids,
            vol.Optional(
                CONF_TRANSITION,
                default=switch._initial_transition,  # pylint: disable=protected-access
            ): VALID_TRANSITION,
            vol.Optional(ATTR_ADAPT_BRIGHTNESS, default=True): cv.boolean,
            vol.Optional(ATTR_ADAPT_COLOR, default=True): cv.boolean,
            vol.Optional(CONF_PREFER_RGB_COLOR, default=False): cv.boolean,
            vol.Optional(CONF_TURN_ON_LIGHTS, default=False): cv.boolean,
        },
        handle_apply,
    )

    platform.async_register_entity_service(
        SERVICE_SET_MANUAL_CONTROL,
        {
            vol.Optional(CONF_LIGHTS, default=[]): cv.entity_ids,
            vol.Optional(CONF_MANUAL_CONTROL, default=True): cv.boolean,
        },
        handle_set_manual_control,
    )


def validate(config_entry: ConfigEntry):
    """Get the options and data from the config_entry and add defaults."""
    defaults = {key: default for key, default, _ in VALIDATION_TUPLES}
    data = deepcopy(defaults)
    data.update(config_entry.options)  # come from options flow
    data.update(config_entry.data)  # all yaml settings come from data
    data = {key: replace_none_str(value) for key, value in data.items()}
    for key, (validate_value, _) in EXTRA_VALIDATION.items():
        value = data.get(key)
        if value is not None:
            data[key] = validate_value(value)  # Fix the types of the inputs
    return data


def match_switch_state_event(event: Event, from_or_to_state: List[str]):
    """Match state event when either 'from_state' or 'to_state' matches."""
    old_state = event.data.get("old_state")
    from_state_match = old_state is not None and old_state.state in from_or_to_state

    new_state = event.data.get("new_state")
    to_state_match = new_state is not None and new_state.state in from_or_to_state

    match = from_state_match or to_state_match
    return match


def _expand_light_groups(hass: HomeAssistant, lights: List[str]) -> List[str]:
    all_lights = set()
    turn_on_off_listener = hass.data[DOMAIN][ATTR_TURN_ON_OFF_LISTENER]
    for light in lights:
        state = hass.states.get(light)
        if state is None:
            _LOGGER.debug("State of %s is None", light)
            all_lights.add(light)
        elif "entity_id" in state.attributes:  # it's a light group
            group = state.attributes["entity_id"]
            turn_on_off_listener.lights.discard(light)
            all_lights.update(group)
            _LOGGER.debug("Expanded %s to %s", light, group)
        else:
            all_lights.add(light)
    return list(all_lights)


def _supported_features(hass: HomeAssistant, light: str):
    state = hass.states.get(light)
    supported_features = state.attributes[ATTR_SUPPORTED_FEATURES]
    return {key for key, value in _SUPPORT_OPTS.items() if supported_features & value}


def color_difference_redmean(
    rgb1: Tuple[float, float, float], rgb2: Tuple[float, float, float]
) -> float:
    """Distance between colors in RGB space (redmean metric).

    The maximal distance between (255, 255, 255) and (0, 0, 0) ≈ 765.

    Sources:
    - https://en.wikipedia.org/wiki/Color_difference#Euclidean
    - https://www.compuphase.com/cmetric.htm
    """
    r_hat = (rgb1[0] + rgb2[0]) / 2
    delta_r, delta_g, delta_b = [(col1 - col2) for col1, col2 in zip(rgb1, rgb2)]
    red_term = (2 + r_hat / 256) * delta_r ** 2
    green_term = 4 * delta_g ** 2
    blue_term = (2 + (255 - r_hat) / 256) * delta_b ** 2
    return math.sqrt(red_term + green_term + blue_term)


def _attributes_have_changed(
    light: str,
    old_attributes: Dict[str, Any],
    new_attributes: Dict[str, Any],
    adapt_brightness: bool,
    adapt_color: bool,
    context: Context,
) -> bool:
    if (
        adapt_brightness
        and ATTR_BRIGHTNESS in old_attributes
        and ATTR_BRIGHTNESS in new_attributes
    ):
        last_brightness = old_attributes[ATTR_BRIGHTNESS]
        current_brightness = new_attributes[ATTR_BRIGHTNESS]
        if abs(current_brightness - last_brightness) > BRIGHTNESS_CHANGE:
            _LOGGER.debug(
                "Brightness of '%s' significantly changed from %s to %s with"
                " context.id='%s'",
                light,
                last_brightness,
                current_brightness,
                context.id,
            )
            return True

    if (
        adapt_brightness
        and ATTR_WHITE_VALUE in old_attributes
        and ATTR_WHITE_VALUE in new_attributes
    ):
        last_white_value = old_attributes[ATTR_WHITE_VALUE]
        current_white_value = new_attributes[ATTR_WHITE_VALUE]
        if abs(current_white_value - last_white_value) > BRIGHTNESS_CHANGE:
            _LOGGER.debug(
                "White Value of '%s' significantly changed from %s to %s with"
                " context.id='%s'",
                light,
                last_white_value,
                current_white_value,
                context.id,
            )
            return True

    if (
        adapt_color
        and ATTR_COLOR_TEMP in old_attributes
        and ATTR_COLOR_TEMP in new_attributes
    ):
        last_color_temp = old_attributes[ATTR_COLOR_TEMP]
        current_color_temp = new_attributes[ATTR_COLOR_TEMP]
        if abs(current_color_temp - last_color_temp) > COLOR_TEMP_CHANGE:
            _LOGGER.debug(
                "Color temperature of '%s' significantly changed from %s to %s with"
                " context.id='%s'",
                light,
                last_color_temp,
                current_color_temp,
                context.id,
            )
            return True

    if (
        adapt_color
        and ATTR_RGB_COLOR in old_attributes
        and ATTR_RGB_COLOR in new_attributes
    ):
        last_rgb_color = old_attributes[ATTR_RGB_COLOR]
        current_rgb_color = new_attributes[ATTR_RGB_COLOR]
        redmean_change = color_difference_redmean(last_rgb_color, current_rgb_color)
        if redmean_change > RGB_REDMEAN_CHANGE:
            _LOGGER.debug(
                "color RGB of '%s' significantly changed from %s to %s with"
                " context.id='%s'",
                light,
                last_rgb_color,
                current_rgb_color,
                context.id,
            )
            return True

    switched_color_temp = (
        ATTR_RGB_COLOR in old_attributes and ATTR_RGB_COLOR not in new_attributes
    )
    switched_to_rgb_color = (
        ATTR_COLOR_TEMP in old_attributes and ATTR_COLOR_TEMP not in new_attributes
    )
    if switched_color_temp or switched_to_rgb_color:
        # Light switched from RGB mode to color_temp or visa versa
        _LOGGER.debug(
            "'%s' switched from RGB mode to color_temp or visa versa",
            light,
        )
        return True
    return False


class AdaptiveSwitch(SwitchEntity, RestoreEntity):
    """Representation of a Adaptive Lighting switch."""

    def __init__(
        self,
        hass,
        config_entry: ConfigEntry,
        turn_on_off_listener: TurnOnOffListener,
        sleep_mode_switch: SimpleSwitch,
        adapt_color_switch: SimpleSwitch,
        adapt_brightness_switch: SimpleSwitch,
    ):
        """Initialize the Adaptive Lighting switch."""
        self.hass = hass
        self.turn_on_off_listener = turn_on_off_listener
        self.sleep_mode_switch = sleep_mode_switch
        self.adapt_color_switch = adapt_color_switch
        self.adapt_brightness_switch = adapt_brightness_switch

        data = validate(config_entry)
        self._name = data[CONF_NAME]
        self._lights = data[CONF_LIGHTS]

        self._detect_non_ha_changes = data[CONF_DETECT_NON_HA_CHANGES]
        self._initial_transition = data[CONF_INITIAL_TRANSITION]
        self._interval = data[CONF_INTERVAL]
        self._only_once = data[CONF_ONLY_ONCE]
        self._prefer_rgb_color = data[CONF_PREFER_RGB_COLOR]
        self._separate_turn_on_commands = data[CONF_SEPARATE_TURN_ON_COMMANDS]
        self._take_over_control = data[CONF_TAKE_OVER_CONTROL]
        self._transition = min(
            data[CONF_TRANSITION], self._interval.total_seconds() // 2
        )

        self._sun_light_settings = SunLightSettings(
            name=self._name,
            astral_location=get_astral_location(self.hass),
            max_brightness=data[CONF_MAX_BRIGHTNESS],
            max_color_temp=data[CONF_MAX_COLOR_TEMP],
            min_brightness=data[CONF_MIN_BRIGHTNESS],
            min_color_temp=data[CONF_MIN_COLOR_TEMP],
            sleep_brightness=data[CONF_SLEEP_BRIGHTNESS],
            sleep_color_temp=data[CONF_SLEEP_COLOR_TEMP],
            sunrise_offset=data[CONF_SUNRISE_OFFSET],
            sunrise_time=data[CONF_SUNRISE_TIME],
            sunset_offset=data[CONF_SUNSET_OFFSET],
            sunset_time=data[CONF_SUNSET_TIME],
            time_zone=self.hass.config.time_zone,
        )

        # Set other attributes
        self._icon = ICON
        self._state = None

        # Tracks 'off' → 'on' state changes
        self._on_to_off_event: Dict[str, Event] = {}
        # Tracks 'on' → 'off' state changes
        self._off_to_on_event: Dict[str, Event] = {}
        # Locks that prevent light adjusting when waiting for a light to 'turn_off'
        self._locks: Dict[str, asyncio.Lock] = {}
        # To count the number of `Context` instances
        self._context_cnt: int = 0

        # Set in self._update_attrs_and_maybe_adapt_lights
        self._settings: Dict[str, Any] = {}

        # Set and unset tracker in async_turn_on and async_turn_off
        self.remove_listeners = []
        _LOGGER.debug(
            "%s: Setting up with '%s',"
            " config_entry.data: '%s',"
            " config_entry.options: '%s', converted to '%s'.",
            self._name,
            self._lights,
            config_entry.data,
            config_entry.options,
            data,
        )

    @property
    def name(self):
        """Return the name of the device if any."""
        return f"Adaptive Lighting: {self._name}"

    @property
    def unique_id(self):
        """Return the unique ID of entity."""
        return self._name

    @property
    def is_on(self) -> Optional[bool]:
        """Return true if adaptive lighting is on."""
        return self._state

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        if self.hass.is_running:
            await self._setup_listeners()
        else:
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, self._setup_listeners
            )
        last_state = await self.async_get_last_state()
        is_new_entry = last_state is None  # newly added to HA
        if is_new_entry or last_state.state == STATE_ON:
            await self.async_turn_on(adapt_lights=not self._only_once)
        else:
            self._state = False
            assert not self.remove_listeners

    async def async_will_remove_from_hass(self):
        """Remove the listeners upon removing the component."""
        self._remove_listeners()

    def _expand_light_groups(self) -> None:
        all_lights = _expand_light_groups(self.hass, self._lights)
        self.turn_on_off_listener.lights.update(all_lights)
        self._lights = list(all_lights)

    async def _setup_listeners(self, _=None) -> None:
        _LOGGER.debug("%s: Called '_setup_listeners'", self._name)
        if not self.is_on or not self.hass.is_running:
            _LOGGER.debug("%s: Cancelled '_setup_listeners'", self._name)
            return

        assert not self.remove_listeners

        remove_interval = async_track_time_interval(
            self.hass, self._async_update_at_interval, self._interval
        )
        remove_sleep = async_track_state_change_event(
            self.hass,
            self.sleep_mode_switch.entity_id,
            self._sleep_mode_switch_state_event,
        )

        self.remove_listeners.extend([remove_interval, remove_sleep])

        if self._lights:
            self._expand_light_groups()
            remove_state = async_track_state_change_event(
                self.hass, self._lights, self._light_event
            )
            self.remove_listeners.append(remove_state)

    def _remove_listeners(self) -> None:
        while self.remove_listeners:
            remove_listener = self.remove_listeners.pop()
            remove_listener()

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the attributes of the switch."""
        if not self.is_on:
            return {key: None for key in self._settings}
        manual_control = [
            light
            for light in self._lights
            if self.turn_on_off_listener.manual_control.get(light)
        ]
        return dict(self._settings, manual_control=manual_control)

    def create_context(self, which: str = "default") -> Context:
        """Create a context that identifies this Adaptive Lighting instance."""
        # Right now the highest number of each context_id it can create is
        # 'adapt_lgt_XXXX_turn_on_9999999999999'
        # 'adapt_lgt_XXXX_interval_999999999999'
        # 'adapt_lgt_XXXX_adapt_lights_99999999'
        # 'adapt_lgt_XXXX_sleep_999999999999999'
        # 'adapt_lgt_XXXX_light_event_999999999'
        # 'adapt_lgt_XXXX_service_9999999999999'
        # So 100 million calls before we run into the 36 chars limit.
        context = create_context(self._name, which, self._context_cnt)
        self._context_cnt += 1
        return context

    async def async_turn_on(  # pylint: disable=arguments-differ
        self, adapt_lights: bool = True
    ) -> None:
        """Turn on adaptive lighting."""
        _LOGGER.debug(
            "%s: Called 'async_turn_on', current state is '%s'", self._name, self._state
        )
        if self.is_on:
            return
        self._state = True
        self.turn_on_off_listener.reset(*self._lights)
        await self._setup_listeners()
        if adapt_lights:
            await self._update_attrs_and_maybe_adapt_lights(
                transition=self._initial_transition,
                force=True,
                context=self.create_context("turn_on"),
            )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off adaptive lighting."""
        if not self.is_on:
            return
        self._state = False
        self._remove_listeners()
        self.turn_on_off_listener.reset(*self._lights)

    async def _async_update_at_interval(self, now=None) -> None:
        await self._update_attrs_and_maybe_adapt_lights(
            force=False, context=self.create_context("interval")
        )

    async def _adapt_light(
        self,
        light: str,
        transition: Optional[int] = None,
        adapt_brightness: Optional[bool] = None,
        adapt_color: Optional[bool] = None,
        prefer_rgb_color: Optional[bool] = None,
        force: bool = False,
        context: Optional[Context] = None,
    ) -> None:
        lock = self._locks.get(light)
        if lock is not None and lock.locked():
            _LOGGER.debug("%s: '%s' is locked", self._name, light)
            return
        service_data = {ATTR_ENTITY_ID: light}
        features = _supported_features(self.hass, light)

        if transition is None:
            transition = self._transition
        if adapt_brightness is None:
            adapt_brightness = self.adapt_brightness_switch.is_on
        if adapt_color is None:
            adapt_color = self.adapt_color_switch.is_on
        if prefer_rgb_color is None:
            prefer_rgb_color = self._prefer_rgb_color

        if "transition" in features:
            service_data[ATTR_TRANSITION] = transition

        if "brightness" in features and adapt_brightness:
            brightness = round(255 * self._settings["brightness_pct"] / 100)
            service_data[ATTR_BRIGHTNESS] = brightness

        if "white_value" in features and adapt_brightness:
            white_value = round(255 * self._settings["brightness_pct"] / 100)
            service_data[ATTR_WHITE_VALUE] = white_value

        if (
            "color_temp" in features
            and adapt_color
            and not (prefer_rgb_color and "color" in features)
        ):
            attributes = self.hass.states.get(light).attributes
            min_mireds, max_mireds = attributes["min_mireds"], attributes["max_mireds"]
            color_temp_mired = self._settings["color_temp_mired"]
            color_temp_mired = max(min(color_temp_mired, max_mireds), min_mireds)
            service_data[ATTR_COLOR_TEMP] = color_temp_mired
        elif "color" in features and adapt_color:
            service_data[ATTR_RGB_COLOR] = self._settings["rgb_color"]

        context = context or self.create_context("adapt_lights")
        if (
            self._take_over_control
            and self._detect_non_ha_changes
            and not force
            and await self.turn_on_off_listener.significant_change(
                self,
                light,
                adapt_brightness,
                adapt_color,
                context,
            )
        ):
            return
        self.turn_on_off_listener.last_service_data[light] = service_data

        async def turn_on(service_data):
            _LOGGER.debug(
                "%s: Scheduling 'light.turn_on' with the following 'service_data': %s"
                " with context.id='%s'",
                self._name,
                service_data,
                context.id,
            )
            await self.hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                service_data,
                context=context,
            )

        if not self._separate_turn_on_commands:
            await turn_on(service_data)
        else:
            # Could be a list of length 1 or 2
            service_datas = _split_service_data(
                service_data, adapt_brightness, adapt_color
            )
            await turn_on(service_datas[0])
            if len(service_datas) == 2:
                transition = service_datas[0].get(ATTR_TRANSITION)
                if transition is not None:
                    await asyncio.sleep(transition)
                await turn_on(service_datas[1])

    async def _update_attrs_and_maybe_adapt_lights(
        self,
        lights: Optional[List[str]] = None,
        transition: Optional[int] = None,
        force: bool = False,
        context: Optional[Context] = None,
    ) -> None:
        assert context is not None
        _LOGGER.debug(
            "%s: '_update_attrs_and_maybe_adapt_lights' called with context.id='%s'",
            self._name,
            context.id,
        )
        assert self.is_on
        self._settings = self._sun_light_settings.get_settings(
            self.sleep_mode_switch.is_on
        )
        self.async_write_ha_state()
        if lights is None:
            lights = self._lights
        if (self._only_once and not force) or not lights:
            return
        await self._adapt_lights(lights, transition, force, context)

    async def _adapt_lights(
        self,
        lights: List[str],
        transition: Optional[int],
        force: bool,
        context: Optional[Context],
    ) -> None:
        assert context is not None
        _LOGGER.debug(
            "%s: '_adapt_lights(%s, %s, force=%s, context.id=%s)' called",
            self.name,
            lights,
            transition,
            force,
            context.id,
        )
        for light in lights:
            if not is_on(self.hass, light):
                continue
            if (
                self._take_over_control
                and self.turn_on_off_listener.is_manually_controlled(
                    self,
                    light,
                    force,
                    self.adapt_brightness_switch.is_on,
                    self.adapt_color_switch.is_on,
                )
            ):
                _LOGGER.debug(
                    "%s: '%s' is being manually controlled, stop adapting, context.id=%s.",
                    self._name,
                    light,
                    context.id,
                )
                continue
            await self._adapt_light(light, transition, force=force, context=context)

    async def _sleep_mode_switch_state_event(self, event: Event) -> None:
        if not match_switch_state_event(event, (STATE_ON, STATE_OFF)):
            return
        _LOGGER.debug(
            "%s: _sleep_mode_switch_state_event, event: '%s'", self._name, event
        )
        # Reset the manually controlled status when the "sleep mode" changes
        self.turn_on_off_listener.reset(*self._lights)
        await self._update_attrs_and_maybe_adapt_lights(
            transition=self._initial_transition,
            force=True,
            context=self.create_context("sleep"),
        )

    async def _light_event(self, event: Event) -> None:
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        entity_id = event.data.get("entity_id")
        if (
            old_state is not None
            and old_state.state == STATE_OFF
            and new_state is not None
            and new_state.state == STATE_ON
        ):
            _LOGGER.debug(
                "%s: Detected an 'off' → 'on' event for '%s' with context.id='%s'",
                self._name,
                entity_id,
                event.context.id,
            )
            self.turn_on_off_listener.reset(entity_id, reset_manual_control=False)
            # Tracks 'off' → 'on' state changes
            self._off_to_on_event[entity_id] = event
            lock = self._locks.get(entity_id)
            if lock is None:
                lock = self._locks[entity_id] = asyncio.Lock()
            async with lock:
                if await self.turn_on_off_listener.maybe_cancel_adjusting(
                    entity_id,
                    off_to_on_event=event,
                    on_to_off_event=self._on_to_off_event.get(entity_id),
                ):
                    # Stop if a rapid 'off' → 'on' → 'off' happens.
                    _LOGGER.debug(
                        "%s: Cancelling adjusting lights for %s", self._name, entity_id
                    )
                    return

            await self._update_attrs_and_maybe_adapt_lights(
                lights=[entity_id],
                transition=self._initial_transition,
                force=True,
                context=self.create_context("light_event"),
            )
        elif (
            old_state is not None
            and old_state.state == STATE_ON
            and new_state is not None
            and new_state.state == STATE_OFF
        ):
            # Tracks 'off' → 'on' state changes
            self._on_to_off_event[entity_id] = event
            self.turn_on_off_listener.reset(entity_id)


class SimpleSwitch(SwitchEntity, RestoreEntity):
    """Representation of a Adaptive Lighting switch."""

    def __init__(
        self, which: str, initial_state: bool, hass: HomeAssistant, config_entry
    ):
        """Initialize the Adaptive Lighting switch."""
        self.hass = hass
        data = validate(config_entry)
        self._icon = ICON
        self._state = None
        self._which = which
        name = data[CONF_NAME]
        self._unique_id = f"{name}_{slugify(self._which)}"
        self._name = f"Adaptive Lighting {which}: {name}"
        self._initial_state = initial_state

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID of entity."""
        return self._unique_id

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def is_on(self) -> Optional[bool]:
        """Return true if adaptive lighting is on."""
        return self._state

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        last_state = await self.async_get_last_state()
        _LOGGER.debug("%s: last state is %s", self._name, last_state)
        if (last_state is None and self._initial_state) or (
            last_state is not None and last_state.state == STATE_ON
        ):
            await self.async_turn_on()
        else:
            await self.async_turn_off()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on adaptive lighting sleep mode."""
        self._state = True

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off adaptive lighting sleep mode."""
        self._state = False


@dataclass(frozen=True)
class SunLightSettings:
    """Track the state of the sun and associated light settings."""

    name: str
    astral_location: astral.Location
    max_brightness: int
    max_color_temp: int
    min_brightness: int
    min_color_temp: int
    sleep_brightness: int
    sleep_color_temp: int
    sunrise_offset: Optional[datetime.timedelta]
    sunrise_time: Optional[datetime.time]
    sunset_offset: Optional[datetime.timedelta]
    sunset_time: Optional[datetime.time]
    time_zone: datetime.tzinfo

    def get_sun_events(self, date: datetime.datetime) -> Dict[str, float]:
        """Get the four sun event's timestamps at 'date'."""

        def _replace_time(date: datetime.datetime, key: str) -> datetime.datetime:
            time = getattr(self, f"{key}_time")
            date_time = datetime.datetime.combine(date, time)
            utc_time = self.time_zone.localize(date_time).astimezone(dt_util.UTC)
            return utc_time

        location = self.astral_location

        sunrise = (
            location.sunrise(date, local=False)
            if self.sunrise_time is None
            else _replace_time(date, "sunrise")
        ) + self.sunrise_offset
        sunset = (
            location.sunset(date, local=False)
            if self.sunset_time is None
            else _replace_time(date, "sunset")
        ) + self.sunset_offset

        if self.sunrise_time is None and self.sunset_time is None:
            solar_noon = location.solar_noon(date, local=False)
            solar_midnight = location.solar_midnight(date, local=False)
        else:
            solar_noon = sunrise + (sunset - sunrise) / 2
            solar_midnight = sunset + ((sunrise + timedelta(days=1)) - sunset) / 2

        events = [
            (SUN_EVENT_SUNRISE, sunrise.timestamp()),
            (SUN_EVENT_SUNSET, sunset.timestamp()),
            (SUN_EVENT_NOON, solar_noon.timestamp()),
            (SUN_EVENT_MIDNIGHT, solar_midnight.timestamp()),
        ]
        # Check whether order is correct
        events = sorted(events, key=lambda x: x[1])
        events_names, _ = zip(*events)
        if events_names not in _ALLOWED_ORDERS:
            msg = (
                f"{self.name}: The sun events {events_names} are not in the expected"
                " order. The Adaptive Lighting integration will not work!"
                " This might happen if your sunrise/sunset offset is too large or"
                " your manually set sunrise/sunset time is past/before noon/midnight."
            )
            _LOGGER.error(msg)
            raise ValueError(msg)

        return events

    def relevant_events(self, now: datetime.datetime) -> List[Tuple[str, float]]:
        """Get the previous and next sun event."""
        events = [
            self.get_sun_events(now + timedelta(days=days)) for days in [-1, 0, 1]
        ]
        events = sum(events, [])  # flatten lists
        events = sorted(events, key=lambda x: x[1])
        i_now = bisect.bisect([ts for _, ts in events], now.timestamp())
        return events[i_now - 1 : i_now + 1]

    def calc_percent(self) -> float:
        """Calculate the position of the sun in %."""
        now = dt_util.utcnow()
        now_ts = now.timestamp()
        today = self.relevant_events(now)
        (_, prev_ts), (next_event, next_ts) = today
        h, x = (  # pylint: disable=invalid-name
            (prev_ts, next_ts)
            if next_event in (SUN_EVENT_SUNSET, SUN_EVENT_SUNRISE)
            else (next_ts, prev_ts)
        )
        k = 1 if next_event in (SUN_EVENT_SUNSET, SUN_EVENT_NOON) else -1
        percentage = (0 - k) * ((now_ts - h) / (h - x)) ** 2 + k
        return percentage

    def calc_brightness_pct(self, percent: float, is_sleep: bool) -> float:
        """Calculate the brightness in %."""
        if is_sleep:
            return self.sleep_brightness
        if percent > 0:
            return self.max_brightness
        delta_brightness = self.max_brightness - self.min_brightness
        percent = 1 + percent
        return (delta_brightness * percent) + self.min_brightness

    def calc_color_temp_kelvin(self, percent: float, is_sleep: bool) -> float:
        """Calculate the color temperature in Kelvin."""
        if is_sleep:
            return self.sleep_color_temp
        if percent > 0:
            delta = self.max_color_temp - self.min_color_temp
            return (delta * percent) + self.min_color_temp
        return self.min_color_temp

    def get_settings(
        self, is_sleep
    ) -> Dict[str, Union[float, Tuple[float, float], Tuple[float, float, float]]]:
        """Get all light settings.

        Calculating all values takes <0.5ms.
        """
        percent = self.calc_percent()
        brightness_pct = self.calc_brightness_pct(percent, is_sleep)
        color_temp_kelvin = self.calc_color_temp_kelvin(percent, is_sleep)
        color_temp_mired: float = color_temperature_kelvin_to_mired(color_temp_kelvin)
        rgb_color: Tuple[float, float, float] = color_temperature_to_rgb(
            color_temp_kelvin
        )
        xy_color: Tuple[float, float] = color_RGB_to_xy(*rgb_color)
        hs_color: Tuple[float, float] = color_xy_to_hs(*xy_color)
        return {
            "brightness_pct": brightness_pct,
            "color_temp_kelvin": color_temp_kelvin,
            "color_temp_mired": color_temp_mired,
            "rgb_color": rgb_color,
            "xy_color": xy_color,
            "hs_color": hs_color,
            "sun_position": percent,
        }


class TurnOnOffListener:
    """Track 'light.turn_off' and 'light.turn_on' service calls."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the TurnOnOffListener that is shared among all switches."""
        self.hass = hass
        self.lights = set()

        # Tracks 'light.turn_off' service calls
        self.turn_off_event: Dict[str, Event] = {}
        # Tracks 'light.turn_on' service calls
        self.turn_on_event: Dict[str, Event] = {}
        # Keep 'asyncio.sleep' tasks that can be cancelled by 'light.turn_on' events
        self.sleep_tasks: Dict[str, asyncio.Task] = {}
        # Tracks which lights are manually controlled
        self.manual_control: Dict[str, bool] = {}
        # Counts the number of times (in a row) a light had a changed state.
        self.cnt_significant_changes: Dict[str, int] = defaultdict(int)
        # Track 'state_changed' events of self.lights resulting from this integration
        self.last_state_change: Dict[str, List[State]] = {}
        # Track last 'service_data' to 'light.turn_on' resulting from this integration
        self.last_service_data: Dict[str, Dict[str, Any]] = {}

        # When a state is different `max_cnt_significant_changes` times in a row,
        # mark it as manually_controlled.
        self.max_cnt_significant_changes = 2

        self.remove_listener = self.hass.bus.async_listen(
            EVENT_CALL_SERVICE, self.turn_on_off_event_listener
        )
        self.remove_listener2 = self.hass.bus.async_listen(
            EVENT_STATE_CHANGED, self.state_changed_event_listener
        )

    def reset(self, *lights, reset_manual_control=True) -> None:
        """Reset the 'manual_control' status of the lights."""
        for light in lights:
            if reset_manual_control:
                self.manual_control[light] = False
            self.last_state_change.pop(light, None)
            self.last_service_data.pop(light, None)
            self.cnt_significant_changes[light] = 0

    async def turn_on_off_event_listener(self, event: Event) -> None:
        """Track 'light.turn_off' and 'light.turn_on' service calls."""
        domain = event.data.get(ATTR_DOMAIN)
        if domain != LIGHT_DOMAIN:
            return

        service = event.data[ATTR_SERVICE]
        service_data = event.data[ATTR_SERVICE_DATA]
        entity_ids = cv.ensure_list_csv(service_data[ATTR_ENTITY_ID])

        if not any(eid in self.lights for eid in entity_ids):
            return

        if service == SERVICE_TURN_OFF:
            transition = service_data.get(ATTR_TRANSITION)
            _LOGGER.debug(
                "Detected an 'light.turn_off('%s', transition=%s)' event with context.id='%s'",
                entity_ids,
                transition,
                event.context.id,
            )
            for eid in entity_ids:
                self.turn_off_event[eid] = event
                self.reset(eid)

        elif service == SERVICE_TURN_ON:
            _LOGGER.debug(
                "Detected an 'light.turn_on('%s')' event with context.id='%s'",
                entity_ids,
                event.context.id,
            )
            for eid in entity_ids:
                task = self.sleep_tasks.get(eid)
                if task is not None:
                    task.cancel()
                self.turn_on_event[eid] = event

    async def state_changed_event_listener(self, event: Event) -> None:
        """Track 'state_changed' events."""
        entity_id = event.data.get(ATTR_ENTITY_ID, "")
        if entity_id not in self.lights or entity_id.split(".")[0] != LIGHT_DOMAIN:
            return

        new_state = event.data.get("new_state")
        if new_state is not None and new_state.state == STATE_ON:
            _LOGGER.debug(
                "Detected a '%s' 'state_changed' event: '%s' with context.id='%s'",
                entity_id,
                new_state.attributes,
                new_state.context.id,
            )

        if (
            new_state is not None
            and new_state.state == STATE_ON
            and is_our_context(new_state.context)
        ):
            # It is possible to have multiple state change events with the same context.
            # This can happen because a `turn_on.light(brightness_pct=100, transition=30)`
            # event leads to an instant state change of
            # `new_state=dict(brightness=100, ...)`. However, after polling the light
            # could still only be `new_state=dict(brightness=50, ...)`.
            # We save all events because the first event change might indicate at what
            # settings the light will be later *or* the second event might indicate a
            # final state. The latter case happens for example when a light was
            # called with a color_temp outside of its range (and HA reports the
            # incorrect 'min_mireds' and 'max_mireds', which happens e.g., for
            # Philips Hue White GU10 Bluetooth lights).
            old_state: Optional[List[State]] = self.last_state_change.get(entity_id)
            if (
                old_state is not None
                and old_state[0].context.id == new_state.context.id
            ):
                # If there is already a state change event from this event (with this
                # context) then append it to the already existing list.
                _LOGGER.debug(
                    "State change event of '%s' is already in 'self.last_state_change' (%s)"
                    " adding this state also",
                    entity_id,
                    new_state.context.id,
                )
                self.last_state_change[entity_id].append(new_state)
            else:
                self.last_state_change[entity_id] = [new_state]

    def is_manually_controlled(
        self,
        switch: AdaptiveSwitch,
        light: str,
        force: bool,
        adapt_brightness: bool,
        adapt_color: bool,
    ) -> bool:
        """Check if the light has been 'on' and is now manually controlled."""
        manual_control = self.manual_control.setdefault(light, False)
        if manual_control:
            # Manually controlled until light is turned on and off
            return True

        turn_on_event = self.turn_on_event.get(light)
        if (
            turn_on_event is not None
            and not is_our_context(turn_on_event.context)
            and not force
        ):
            keys = turn_on_event.data[ATTR_SERVICE_DATA].keys()
            if (adapt_color and COLOR_ATTRS.intersection(keys)) or (
                adapt_brightness and BRIGHTNESS_ATTRS.intersection(keys)
            ):
                # Light was already on and 'light.turn_on' was not called by
                # the adaptive_lighting integration.
                manual_control = self.manual_control[light] = True
                _fire_manual_control_event(switch, light, turn_on_event.context)
                _LOGGER.debug(
                    "'%s' was already on and 'light.turn_on' was not called by the"
                    " adaptive_lighting integration (context.id='%s'), the Adaptive"
                    " Lighting will stop adapting the light until the switch or the"
                    " light turns off and then on again.",
                    light,
                    turn_on_event.context.id,
                )
        return manual_control

    async def significant_change(
        self,
        switch: AdaptiveSwitch,
        light: str,
        adapt_brightness: bool,
        adapt_color: bool,
        context: Context,
    ) -> bool:
        """Has the light made a significant change since last update.

        This method will detect changes that were made to the light without
        calling 'light.turn_on', so outside of Home Assistant. If a change is
        detected, we mark the light as 'manually controlled' until the light
        or switch is turned 'off' and 'on' again.
        """
        if light not in self.last_state_change:
            return False
        old_states: List[State] = self.last_state_change[light]
        await self.hass.helpers.entity_component.async_update_entity(light)
        new_state = self.hass.states.get(light)
        compare_to = functools.partial(
            _attributes_have_changed,
            light=light,
            new_attributes=new_state.attributes,
            adapt_brightness=adapt_brightness,
            adapt_color=adapt_color,
            context=context,
        )
        for index, old_state in enumerate(old_states):
            changed = compare_to(old_attributes=old_state.attributes)
            if not changed:
                _LOGGER.debug(
                    "State of '%s' didn't change wrt change event nr. %s (context.id=%s)",
                    light,
                    index,
                    context.id,
                )
                break

        last_service_data = self.last_service_data.get(light)
        if changed and last_service_data is not None:
            # It can happen that the state change events that are associated
            # with the last 'light.turn_on' call by this integration were not
            # final states. Possibly a later EVENT_STATE_CHANGED happened, where
            # the correct target brightness/color was reached.
            changed = compare_to(old_attributes=last_service_data)
            if not changed:
                _LOGGER.debug(
                    "State of '%s' didn't change wrt 'last_service_data' (context.id=%s)",
                    light,
                    context.id,
                )

        n_changes = self.cnt_significant_changes[light]
        if changed:
            self.cnt_significant_changes[light] += 1
            if n_changes >= self.max_cnt_significant_changes:
                # Only mark a light as significantly changing, if changed==True
                # N times in a row. We do this because sometimes a state changes
                # happens only *after* a new update interval has already started.
                self.manual_control[light] = True
                _fire_manual_control_event(switch, light, context, is_async=False)
        else:
            if n_changes > 1:
                _LOGGER.debug(
                    "State of '%s' had 'cnt_significant_changes=%s' but the state"
                    " changed to the expected settings now",
                    light,
                    n_changes,
                )
            self.cnt_significant_changes[light] = 0

        return changed

    async def maybe_cancel_adjusting(
        self, entity_id: str, off_to_on_event: Event, on_to_off_event: Optional[Event]
    ) -> bool:
        """Cancel the adjusting of a light if it has just been turned off.

        Possibly the lights just got a 'turn_off' call, however, the light
        is actually still turning off (e.g., because of a 'transition') and
        HA polls the light before the light is 100% off. This might trigger
        a rapid switch 'off' → 'on' → 'off'. To prevent this component
        from interfering on the 'on' state, we make sure to wait at least
        TURNING_OFF_DELAY (or the 'turn_off' transition time) between a
        'off' → 'on' event and then check whether the light is still 'on' or
        if the brightness is still decreasing. Only if it is the case we
        adjust the lights.
        """
        if on_to_off_event is None:
            # No state change has been registered before.
            return False

        id_on_to_off = on_to_off_event.context.id

        turn_off_event = self.turn_off_event.get(entity_id)
        if turn_off_event is not None:
            transition = turn_off_event.data[ATTR_SERVICE_DATA].get(ATTR_TRANSITION)
        else:
            transition = None

        turn_on_event = self.turn_on_event.get(entity_id)
        id_turn_on = turn_on_event.context.id

        id_off_to_on = off_to_on_event.context.id

        if id_off_to_on == id_turn_on and id_off_to_on is not None:
            # State change 'off' → 'on' triggered by 'light.turn_on'.
            return False

        if (
            turn_off_event is not None
            and id_on_to_off == turn_off_event.context.id
            and id_on_to_off is not None
            and transition is not None  # 'turn_off' is called with transition=...
        ):
            # State change 'on' → 'off' and 'light.turn_off(..., transition=...)' come
            # from the same event, so wait at least the 'turn_off' transition time.
            delay = max(transition, TURNING_OFF_DELAY)
        else:
            # State change 'off' → 'on' happened because the light state was set.
            # Possibly because of polling.
            delay = TURNING_OFF_DELAY

        delta_time = (dt_util.utcnow() - on_to_off_event.time_fired).total_seconds()
        if delta_time > delay:
            return False

        # Here we could just `return True` but because we want to prevent any updates
        # from happening to this light (through async_track_time_interval or
        # sleep_state) for some time, we wait below until the light
        # is 'off' or the time has passed.

        delay -= delta_time  # delta_time has passed since the 'off' → 'on' event
        _LOGGER.debug("Waiting with adjusting '%s' for %s", entity_id, delay)

        for _ in range(3):
            # It can happen that the actual transition time is longer than the
            # specified time in the 'turn_off' service.
            coro = asyncio.sleep(delay)
            task = self.sleep_tasks[entity_id] = asyncio.ensure_future(coro)
            try:
                await task
            except asyncio.CancelledError:  # 'light.turn_on' has been called
                _LOGGER.debug(
                    "Sleep task is cancelled due to 'light.turn_on('%s')' call",
                    entity_id,
                )
                return False

            if not is_on(self.hass, entity_id):
                return True
            delay = TURNING_OFF_DELAY  # next time only wait this long

        if transition is not None:
            # Always ignore when there's a 'turn_off' transition.
            # Because it seems like HA cannot detect whether a light is
            # transitioning into 'off'. Maybe needs some discussion/input?
            return True

        # Now we assume that the lights are still on and they were intended
        # to be on. In case this still gives problems for some, we might
        # choose to **only** adapt on 'light.turn_on' events and ignore
        # other 'off' → 'on' state switches resulting from polling. That
        # would mean we 'return True' here.
        return False
