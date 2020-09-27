"""Adaptive Lighting Component for Home-Assistant."""

import asyncio
import bisect
from copy import deepcopy
from datetime import timedelta
import logging
from typing import Dict, Tuple

import voluptuous as vol

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_TEMP,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_TRANSITION,
    VALID_TRANSITION,
    is_on,
)
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_SERVICE,
    ATTR_SERVICE_DATA,
    CONF_NAME,
    EVENT_CALL_SERVICE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change,
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
    CONF_COLORS_ONLY,
    CONF_DISABLE_BRIGHTNESS_ADJUST,
    CONF_DISABLE_COLOR_ADJUST,
    CONF_DISABLE_ENTITY,
    CONF_DISABLE_STATE,
    CONF_INITIAL_TRANSITION,
    CONF_INTERVAL,
    CONF_LIGHTS,
    CONF_MAX_BRIGHTNESS,
    CONF_MAX_COLOR_TEMP,
    CONF_MIN_BRIGHTNESS,
    CONF_MIN_COLOR_TEMP,
    CONF_ON_LIGHTS_ONLY,
    CONF_ONLY_ONCE,
    CONF_SLEEP_BRIGHTNESS,
    CONF_SLEEP_COLOR_TEMP,
    CONF_SLEEP_ENTITY,
    CONF_SLEEP_STATE,
    CONF_SUNRISE_OFFSET,
    CONF_SUNRISE_TIME,
    CONF_SUNSET_OFFSET,
    CONF_SUNSET_TIME,
    CONF_TRANSITION,
    DOMAIN,
    EXTRA_VALIDATION,
    ICON,
    SERVICE_APPLY,
    SUN_EVENT_MIDNIGHT,
    SUN_EVENT_NOON,
    TURNING_OFF_DELAY,
    VALIDATION_TUPLES,
    replace_none_str,
)

_SUPPORT_OPTS = {
    "brightness": SUPPORT_BRIGHTNESS,
    "color_temp": SUPPORT_COLOR_TEMP,
    "color": SUPPORT_COLOR,
    "transition": SUPPORT_TRANSITION,
}

_ORDER = (SUN_EVENT_SUNRISE, SUN_EVENT_NOON, SUN_EVENT_SUNSET, SUN_EVENT_MIDNIGHT)
_ALLOWED_ORDERS = {_ORDER[i:] + _ORDER[:i] for i in range(len(_ORDER))}

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


async def handle_apply(switch, service_call):
    """Handle the entity service apply."""
    if not isinstance(switch, AdaptiveSwitch):
        raise ValueError("Apply can only be called for a AdaptiveSwitch.")
    data = service_call.data
    tasks = [
        await switch._adjust_light(  # pylint: disable=protected-access
            light,
            data[CONF_TRANSITION],
            data[CONF_COLORS_ONLY],
        )
        for light in data[CONF_LIGHTS]
        if not data[CONF_ON_LIGHTS_ONLY] or is_on(switch.hass, light)
    ]
    if tasks:
        await asyncio.wait(tasks)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the AdaptiveLighting switch."""
    switch = AdaptiveSwitch(hass, config_entry)
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    name = config_entry.data[CONF_NAME]
    hass.data[DOMAIN][name] = switch

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
            vol.Optional(CONF_COLORS_ONLY, default=False): cv.boolean,
            vol.Optional(CONF_ON_LIGHTS_ONLY, default=False): cv.boolean,
        },
        handle_apply,
    )
    async_add_entities([switch], update_before_add=True)


def validate(config_entry):
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


class AdaptiveSwitch(SwitchEntity, RestoreEntity):
    """Representation of a Adaptive Lighting switch."""

    def __init__(self, hass, config_entry):
        """Initialize the Adaptive Lighting switch."""
        self.hass = hass

        data = validate(config_entry)
        self._name = data[CONF_NAME]
        self._lights = data[CONF_LIGHTS]
        self._disable_brightness_adjust = data[CONF_DISABLE_BRIGHTNESS_ADJUST]
        self._disable_color_adjust = data[CONF_DISABLE_COLOR_ADJUST]
        self._disable_entity = data[CONF_DISABLE_ENTITY]
        self._disable_state = data[CONF_DISABLE_STATE]
        self._initial_transition = data[CONF_INITIAL_TRANSITION]
        self._interval = data[CONF_INTERVAL]
        self._max_brightness = data[CONF_MAX_BRIGHTNESS]
        self._max_color_temp = data[CONF_MAX_COLOR_TEMP]
        self._min_brightness = data[CONF_MIN_BRIGHTNESS]
        self._min_color_temp = data[CONF_MIN_COLOR_TEMP]
        self._only_once = data[CONF_ONLY_ONCE]
        self._sleep_brightness = data[CONF_SLEEP_BRIGHTNESS]
        self._sleep_color_temp = data[CONF_SLEEP_COLOR_TEMP]
        self._sleep_entity = data[CONF_SLEEP_ENTITY]
        self._sleep_state = data[CONF_SLEEP_STATE]
        self._sunrise_offset = data[CONF_SUNRISE_OFFSET]
        self._sunrise_time = data[CONF_SUNRISE_TIME]
        self._sunset_offset = data[CONF_SUNSET_OFFSET]
        self._sunset_time = data[CONF_SUNSET_TIME]
        self._transition = data[CONF_TRANSITION]

        # Set other attributes
        self._icon = ICON
        self._entity_id = f"switch.{DOMAIN}_{slugify(self._name)}"

        # Tracks 'off' → 'on' state changes
        self._on_to_off_event: Dict[str, Tuple[float, str]] = {}
        # Tracks 'light.turn_off(..., transition=...)' service calls
        self._turn_off_service_event: Dict[str, Tuple[str, float]] = {}

        # Initialize attributes that will be set in self._update_attrs
        self._percent = None
        self._brightness = None
        self._color_temp_kelvin = None
        self._color_temp_mired = None
        self._rgb_color = None
        self._xy_color = None
        self._hs_color = None

        # Set and unset tracker in async_turn_on and async_turn_off
        self.unsub_tracker = None
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
    def entity_id(self):
        """Return the entity ID of the switch."""
        return self._entity_id

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if adaptive lighting is on."""
        return self.unsub_tracker is not None

    def _supported_features(self, light):
        state = self.hass.states.get(light)
        supported_features = state.attributes["supported_features"]
        return {
            key for key, value in _SUPPORT_OPTS.items() if supported_features & value
        }

    def _unpack_light_groups(self, lights):
        all_lights = []
        for light in lights:
            state = self.hass.states.get(light)
            if state is None:
                _LOGGER.debug("%s: State of %s is None", self._name, light)
                # TODO: make sure that the lights are loaded when doing this
                all_lights.append(light)
            elif "entity_id" in state.attributes:  # it's a light group
                group = state.attributes["entity_id"]
                _LOGGER.debug("%s: Unpacked %s to %s", self._name, lights, group)
                all_lights.extend(group)
            else:
                all_lights.append(light)
        return all_lights

    async def async_added_to_hass(self):
        """Call when entity about to be added to hass."""
        if self._lights:
            unpacked_lights = self._unpack_light_groups(self._lights)
            async_track_state_change_event(
                self.hass, unpacked_lights, self._light_event
            )
            # Tracks 'light.turn_off(..., transition=...)' service calls
            self.hass.bus.async_listen(
                EVENT_CALL_SERVICE, self._turn_off_event_listener
            )
            track_kwargs = dict(hass=self.hass, action=self._state_changed)
            if self._sleep_entity is not None:
                sleep_kwargs = dict(track_kwargs, entity_ids=self._sleep_entity)
                async_track_state_change(**sleep_kwargs, to_state=self._sleep_state)
                async_track_state_change(**sleep_kwargs, from_state=self._sleep_state)

            if self._disable_entity is not None:
                disable_kwargs = dict(track_kwargs, entity_ids=self._disable_entity)
                async_track_state_change(
                    **disable_kwargs, from_state=self._disable_state
                )
                async_track_state_change(**disable_kwargs, to_state=self._disable_state)

        last_state = await self.async_get_last_state()
        if last_state and last_state.state == STATE_ON:
            await self.async_turn_on()

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the attributes of the switch."""
        attrs = {
            "percent": self._percent,
            "brightness": self._brightness,
            "color_temp_kelvin": self._color_temp_kelvin,
            "color_temp_mired": self._color_temp_mired,
            "rgb_color": self._rgb_color,
            "xy_color": self._xy_color,
            "hs_color": self._hs_color,
        }
        if not self.is_on:
            return {key: None for key in attrs}
        return attrs

    async def async_turn_on(self, **kwargs):
        """Turn on adaptive lighting."""
        await self._update_lights(transition=self._initial_transition, force=True)
        self.unsub_tracker = async_track_time_interval(
            self.hass, self._async_update_at_interval, self._interval
        )

    async def async_turn_off(self, **kwargs):
        """Turn off adaptive lighting."""
        if self.is_on:
            self.unsub_tracker()
            self.unsub_tracker = None

    async def _update_attrs(self):
        """Update Adaptive Values."""
        # Setting all values because this method takes <0.5ms to execute.
        self._percent = self._calc_percent()
        self._brightness = self._calc_brightness()
        self._color_temp_kelvin = self._calc_color_temp_kelvin()
        self._color_temp_mired = color_temperature_kelvin_to_mired(
            self._color_temp_kelvin
        )
        self._rgb_color = color_temperature_to_rgb(self._color_temp_kelvin)
        self._xy_color = color_RGB_to_xy(*self._rgb_color)
        self._hs_color = color_xy_to_hs(*self._xy_color)
        self.async_write_ha_state()
        _LOGGER.debug("%s: '_update_attrs' called", self._name)

    async def _async_update_at_interval(self, now=None):
        await self._update_lights(force=False)

    async def _update_lights(self, lights=None, transition=None, force=False):
        await self._update_attrs()
        if self._only_once and not force:
            return
        await self._adjust_lights(lights or self._lights, transition)

    def _get_sun_events(self, date):
        def _replace_time(date, key):
            other_date = getattr(self, f"_{key}_time")
            return date.replace(
                hour=other_date.hour,
                minute=other_date.minute,
                second=other_date.second,
                microsecond=other_date.microsecond,
            )

        location = get_astral_location(self.hass)
        sunrise = (
            location.sunrise(date, local=False)
            if self._sunrise_time is None
            else _replace_time(date, "sunrise")
        ) + self._sunrise_offset
        sunset = (
            location.sunset(date, local=False)
            if self._sunset_time is None
            else _replace_time(date, "sunset")
        ) + self._sunset_offset

        if self._sunrise_time is None and self._sunset_time is None:
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
        assert events_names in _ALLOWED_ORDERS, events_names

        return events

    def _relevant_events(self, now):
        events = [
            self._get_sun_events(now + timedelta(days=days)) for days in [-1, 0, 1]
        ]
        events = sum(events, [])  # flatten lists
        events = sorted(events, key=lambda x: x[1])
        i_now = bisect.bisect([ts for _, ts in events], now.timestamp())
        return events[i_now - 1 : i_now + 1]

    def _calc_percent(self):
        now = dt_util.utcnow()
        now_ts = now.timestamp()
        today = self._relevant_events(now)
        (_, prev_ts), (next_event, next_ts) = today
        h, x = (  # pylint: disable=invalid-name
            (prev_ts, next_ts)
            if next_event in (SUN_EVENT_SUNSET, SUN_EVENT_SUNRISE)
            else (next_ts, prev_ts)
        )
        k = 1 if next_event in (SUN_EVENT_SUNSET, SUN_EVENT_NOON) else -1
        percentage = (0 - k) * ((now_ts - h) / (h - x)) ** 2 + k
        return percentage

    def _is_sleep(self):
        return (
            self._sleep_entity is not None
            and self.hass.states.get(self._sleep_entity).state in self._sleep_state
        )

    def _calc_color_temp_kelvin(self):
        if self._is_sleep():
            return self._sleep_color_temp
        if self._percent > 0:
            delta = self._max_color_temp - self._min_color_temp
            return (delta * self._percent) + self._min_color_temp
        return self._min_color_temp

    def _calc_brightness(self) -> float:
        if self._disable_brightness_adjust:
            return
        if self._is_sleep():
            return self._sleep_brightness
        if self._percent > 0:
            return self._max_brightness
        delta_brightness = self._max_brightness - self._min_brightness
        percent = 1 + self._percent
        return (delta_brightness * percent) + self._min_brightness

    def _is_disabled(self):
        return (
            self._disable_entity is not None
            and self.hass.states.get(self._disable_entity).state in self._disable_state
        )

    async def _adjust_light(self, light, transition, colors_only=False):
        service_data = {ATTR_ENTITY_ID: light}
        features = self._supported_features(light)

        if "transition" in features:
            if transition is None:
                transition = self._transition
            service_data[ATTR_TRANSITION] = transition

        if (
            self._brightness is not None
            and "brightness" in features
            and not colors_only
        ):
            service_data[ATTR_BRIGHTNESS_PCT] = self._brightness

        if "color" in features and not self._disable_color_adjust:
            service_data[ATTR_RGB_COLOR] = self._rgb_color
        elif "color_temp" in features:
            service_data[ATTR_COLOR_TEMP] = self._color_temp_mired

        _LOGGER.debug(
            "%s: Scheduling 'light.turn_on' with the following 'service_data': %s",
            self._name,
            service_data,
        )
        return self.hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_ON, service_data
        )

    def _should_adjust(self):
        if not self._lights or not self.is_on or self._is_disabled():
            return False
        return True

    async def _adjust_lights(self, lights, transition):
        if not self._should_adjust():
            return
        tasks = [
            await self._adjust_light(light, transition)
            for light in lights
            if is_on(self.hass, light)
        ]
        if tasks:
            await asyncio.wait(tasks)

    async def _state_changed(self, entity_id, from_state, to_state):
        _LOGGER.debug(
            "%s: _state_changed, from_state: '%s', to_state: '%s'",
            self._name,
            from_state,
            to_state,
        )
        await self._update_lights(transition=self._initial_transition, force=True)

    async def _light_event(self, event):
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        entity_id = event.data.get("entity_id")
        now_ts = dt_util.now().timestamp()
        if (
            old_state is not None
            and old_state.state == "off"
            and new_state is not None
            and new_state.state == "on"
        ):
            _LOGGER.debug(
                "%s: Detected an 'off' → 'on' event for '%s'", self._name, entity_id
            )
            if await self._maybe_cancel(entity_id, now_ts):
                # Stop if a rapid 'off' → 'on' → 'off' happens.
                _LOGGER.debug(
                    "%s: Cancelling adjusting lights for %s", self._name, entity_id
                )
                return
            await self._update_lights(
                lights=[entity_id],
                transition=self._initial_transition,
                force=True,
            )
        elif (
            old_state is not None
            and old_state.state == "on"
            and new_state is not None
            and new_state.state == "off"
        ):
            # Tracks 'off' → 'on' state changes
            self._on_to_off_event[entity_id] = (now_ts, event.context.id)

    async def _maybe_cancel(self, entity_id, now_ts) -> bool:
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
        ts_on_to_off, id_on_to_off = self._on_to_off_event.get(entity_id, (0, None))
        id_turn_off, transition = self._turn_off_service_event.get(
            entity_id, (None, None)
        )
        if (
            id_on_to_off is not None
            and id_turn_off is not None
            and id_on_to_off == id_turn_off
        ):
            # State change 'off' → 'on' and 'light.turn_off(..., transition=...)' are
            # from the same event, so wait at least the 'turn_off' transition time.
            delay = transition
        elif ts_on_to_off == 0:
            # No state change has been registered before.
            return False
        else:
            # State change 'off' → 'on' happened but **not** because a
            # 'light.turn_off' event that is called with 'transition'.
            delay = TURNING_OFF_DELAY

        delta_time = now_ts - ts_on_to_off
        if delta_time > delay:
            return False
        delay -= delta_time  # delta_time has passed since the 'off' → 'on' event
        _LOGGER.debug(
            "%s: Waiting with adjusting '%s' for %s.", self._name, entity_id, delay
        )
        current_state = self.hass.states.get(entity_id)
        _LOGGER.debug(
            "%s: '%s' state before sleep is '%s'",
            self._name,
            entity_id,
            current_state,
        )
        for _ in range(3):
            # It can happen that the actual transition time is longer than the
            # specified time in the 'turn_off' service, so we check whether the
            # brightness is still going down, if so, we wait a little longer.
            await asyncio.sleep(delay)
            await self.hass.services.async_call(
                HA_DOMAIN,
                SERVICE_UPDATE_ENTITY,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
            old_state = current_state
            current_state = self.hass.states.get(entity_id)
            if current_state.state == "off":
                return True
            old_brightness = old_state.attributes.get(ATTR_BRIGHTNESS, 0)
            current_brightness = current_state.attributes.get(ATTR_BRIGHTNESS, 0)
            brightness_going_down = old_brightness > current_brightness
            _LOGGER.debug(
                "%s: '%s' state after sleep is '%s'",
                self._name,
                entity_id,
                current_state,
            )
            if not brightness_going_down:
                break
            delay = TURNING_OFF_DELAY  # next time only wait this long

        if transition is not None:
            # Always ignore when there's a transition and light is still on.
            # TODO: I am doing this because it seems like HA cannot detect
            # whether a light is transitioning into 'off'. Because in my
            # tests `brightness_going_down == False` even when it is actually
            # still going down... Needs some discussion.
            return True

        return current_state.state == "off"

    async def _turn_off_event_listener(self, event):
        """Track 'light.turn_off(..., transition=...)' service calls."""
        if event.data.get(ATTR_DOMAIN) != LIGHT_DOMAIN:
            return
        if event.data.get(ATTR_SERVICE) != SERVICE_TURN_OFF:
            return
        service_data = event.data.get(ATTR_SERVICE_DATA, {})
        transition = service_data.get(ATTR_TRANSITION)
        if transition is not None and transition > 0:
            entity_id = service_data[ATTR_ENTITY_ID]
            _LOGGER.debug(
                "%s: Detected an 'light.turn_off('%s', transition=%s)' event",
                self._name,
                entity_id,
                transition,
            )
            if isinstance(entity_id, str):
                entity_id = [entity_id]
            for eid in entity_id:
                self._turn_off_service_event[eid] = (event.context.id, transition)
