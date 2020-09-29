"""Switch for the Adaptive Lighting integration."""

import asyncio
import bisect
from copy import deepcopy
import datetime
from datetime import timedelta
import logging
from typing import Dict, Tuple

import voluptuous as vol

from homeassistant.components.light import (
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
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_SERVICE,
    ATTR_SERVICE_DATA,
    CONF_NAME,
    EVENT_CALL_SERVICE,
    EVENT_HOMEASSISTANT_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import Context, Event
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
    ATTR_TURN_ON_OFF_LISTENER,
    CONF_ADJUST_BRIGHTNESS,
    CONF_ADJUST_COLOR_TEMP,
    CONF_ADJUST_RGB_COLOR,
    CONF_COLORS_ONLY,
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
    CONF_PREFER_RGB_COLOR,
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
    data = hass.data[DOMAIN]

    if ATTR_TURN_ON_OFF_LISTENER not in data:
        data[ATTR_TURN_ON_OFF_LISTENER] = TurnOnOffListener(hass)
    turn_on_off_listener = data[ATTR_TURN_ON_OFF_LISTENER]

    switch = AdaptiveSwitch(hass, config_entry, turn_on_off_listener)
    data[config_entry.entry_id][SWITCH_DOMAIN] = switch

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

    def __init__(self, hass, config_entry, turn_on_off_listener):
        """Initialize the Adaptive Lighting switch."""
        self.hass = hass
        self.turn_on_off_listener = turn_on_off_listener

        data = validate(config_entry)
        self._name = data[CONF_NAME]
        self._lights = data[CONF_LIGHTS]
        self._adjust_brightness = data[CONF_ADJUST_BRIGHTNESS]
        self._adjust_color_temp = data[CONF_ADJUST_COLOR_TEMP]
        self._adjust_rgb_color = data[CONF_ADJUST_RGB_COLOR]
        self._disable_entity = data[CONF_DISABLE_ENTITY]
        self._disable_state = data[CONF_DISABLE_STATE]
        self._initial_transition = data[CONF_INITIAL_TRANSITION]
        self._interval = data[CONF_INTERVAL]
        self._max_brightness = data[CONF_MAX_BRIGHTNESS]
        self._max_color_temp = data[CONF_MAX_COLOR_TEMP]
        self._min_brightness = data[CONF_MIN_BRIGHTNESS]
        self._min_color_temp = data[CONF_MIN_COLOR_TEMP]
        self._only_once = data[CONF_ONLY_ONCE]
        self._prefer_rgb_color = data[CONF_PREFER_RGB_COLOR]
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
        self._state = None

        # Tracks 'off' → 'on' state changes
        self._on_to_off_event: Dict[str, Event] = {}
        # Locks that prevent light adjusting when waiting for a light to 'turn_off'
        self._locks: Dict[str, asyncio.Lock] = {}

        # Initialize attributes that will be set in self._update_attrs
        self._percent = None
        self._brightness = None
        self._color_temp_kelvin = None
        self._color_temp_mired = None
        self._rgb_color = None
        self._xy_color = None
        self._hs_color = None

        # Set and unset tracker in async_turn_on and async_turn_off
        self.unsub_trackers = []
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
        return self._state

    def _supported_features(self, light):
        state = self.hass.states.get(light)
        supported_features = state.attributes["supported_features"]
        return {
            key for key, value in _SUPPORT_OPTS.items() if supported_features & value
        }

    async def async_added_to_hass(self):
        """Call when entity about to be added to hass."""
        if self._lights:
            if self.hass.is_running:
                await self._setup_trackers()
            else:
                self.hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_START, self._setup_trackers
                )
        last_state = await self.async_get_last_state()
        if last_state and last_state.state == STATE_ON:
            self._state = True
            await self.async_turn_on(
                adjust_lights=not self._only_once,
                setup_listeners=False,
            )
        else:
            self._state = False

    def _unpack_light_groups(self) -> None:
        all_lights = set()
        for light in self._lights:
            state = self.hass.states.get(light)
            if state is None:
                _LOGGER.debug("%s: State of %s is None", self._name, light)
                all_lights.add(light)
            elif "entity_id" in state.attributes:  # it's a light group
                group = state.attributes["entity_id"]
                all_lights.update(group)
                _LOGGER.debug("%s: Unpacked %s to %s", self._name, light, group)
            else:
                all_lights.add(light)
        self.turn_on_off_listener.lights.update(all_lights)
        self._lights = list(all_lights)

    async def _setup_trackers(self, _=None):
        assert not self.unsub_trackers
        self._unpack_light_groups()
        rm_interval = async_track_time_interval(
            self.hass, self._async_update_at_interval, self._interval
        )
        rm_state = async_track_state_change_event(
            self.hass, self._lights, self._light_event
        )
        self.unsub_trackers.extend([rm_interval, rm_state])
        track_kwargs = dict(hass=self.hass, action=self._state_changed)
        if self._sleep_entity is not None:
            kwgs = dict(track_kwargs, entity_ids=self._sleep_entity)
            rm_from = async_track_state_change(**kwgs, from_state=self._sleep_state)
            rm_to = async_track_state_change(**kwgs, to_state=self._sleep_state)
            self.unsub_trackers.extend([rm_from, rm_to])
        if self._disable_entity is not None:
            kwgs = dict(track_kwargs, entity_ids=self._disable_entity)
            rm_from = async_track_state_change(**kwgs, from_state=self._disable_state)
            rm_to = async_track_state_change(**kwgs, to_state=self._disable_state)
            self.unsub_trackers.extend([rm_from, rm_to])

    def _unsub_trackers(self):
        while self.unsub_trackers:
            unsub = self.unsub_trackers.pop()
            unsub()

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

    async def async_turn_on(
        self, adjust_lights=True, setup_listeners=True
    ):  # pylint: disable=arguments-differ
        """Turn on adaptive lighting."""
        if self.is_on:
            return
        self._state = True
        if setup_listeners:
            await self._setup_trackers()
        if adjust_lights:
            await self._update_lights(transition=self._initial_transition, force=True)

    async def async_turn_off(self, **kwargs):
        """Turn off adaptive lighting."""
        if not self.is_on:
            return
        self._state = False
        self._unsub_trackers()

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
            time = getattr(self, f"_{key}_time")
            date_time = datetime.datetime.combine(datetime.date.today(), time)
            time_zone = self.hass.config.time_zone
            utc_time = time_zone.localize(date_time).astimezone(dt_util.UTC)
            return date.replace(
                hour=utc_time.hour,
                minute=utc_time.minute,
                second=utc_time.second,
                microsecond=utc_time.microsecond,
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

        if "brightness" in features and self._adjust_brightness and not colors_only:
            service_data[ATTR_BRIGHTNESS_PCT] = self._brightness

        if (
            "color_temp" in features
            and self._adjust_color_temp
            and not (self._prefer_rgb_color and "color" in features)
        ):
            attributes = self.hass.states.get(light).attributes
            min_mireds, max_mireds = attributes["min_mireds"], attributes["max_mireds"]
            color_temp_mired = max(min(self._color_temp_mired, max_mireds), min_mireds)
            service_data[ATTR_COLOR_TEMP] = color_temp_mired
        elif "color" in features and self._adjust_rgb_color:
            service_data[ATTR_RGB_COLOR] = self._rgb_color

        _LOGGER.debug(
            "%s: Scheduling 'light.turn_on' with the following 'service_data': %s",
            self._name,
            service_data,
        )

        return self.hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            service_data,
            context=Context(),
        )

    def _should_adjust(self):
        if not self._lights or not self.is_on or self._is_disabled():
            return False
        return True

    async def _adjust_lights(self, lights, transition):
        if not self._should_adjust():
            return
        _LOGGER.debug(
            "%s: '_adjust_lights(%s, %s)' called", self.name, lights, transition
        )
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
        lock = self._locks.get(entity_id)
        if lock is not None and lock.locked:
            return
        await self._update_lights(transition=self._initial_transition, force=True)

    async def _light_event(self, event):
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        entity_id = event.data.get("entity_id")
        if (
            old_state is not None
            and old_state.state == "off"
            and new_state is not None
            and new_state.state == "on"
        ):
            _LOGGER.debug(
                "%s: Detected an 'off' → 'on' event for '%s'", self._name, entity_id
            )
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
            self._on_to_off_event[entity_id] = event


class TurnOnOffListener:
    """Track 'light.turn_off' and 'light.turn_on' service calls."""

    def __init__(self, hass):
        """Initialize the TurnOnOffListener that is shared among all switches."""
        self.hass = hass
        self.lights = set()

        # Tracks 'light.turn_off' service calls
        self.turn_off_event: Dict[str, Tuple[str, float]] = {}
        # Tracks 'light.turn_on' service calls
        self.turn_on_event: Dict[str, Tuple[str]] = {}

        self.sleep_tasks: Dict[str, asyncio.Task] = {}

        self.hass.bus.async_listen(EVENT_CALL_SERVICE, self.turn_on_off_event_listener)

    async def maybe_cancel_adjusting(
        self, entity_id, off_to_on_event, on_to_off_event
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
        id_turn_off, transition = self.turn_off_event.get(entity_id, (None, None))
        id_turn_on = self.turn_on_event.get(entity_id)
        id_off_to_on = off_to_on_event.context.id

        if id_off_to_on == id_turn_on and id_off_to_on is not None:
            # State change 'off' → 'on' triggered by 'light.turn_on'.
            return False

        if (
            id_on_to_off == id_turn_off
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
        # sleep_state or disable_state) for some time, we wait below until the light
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

        return False

    async def turn_on_off_event_listener(self, event):
        """Track 'light.turn_off' and 'light.turn_on' service calls."""
        domain = event.data.get(ATTR_DOMAIN)
        if domain != LIGHT_DOMAIN:
            return

        service = event.data.get(ATTR_SERVICE)
        service_data = event.data.get(ATTR_SERVICE_DATA, {})

        entity_ids = service_data.get(ATTR_ENTITY_ID)
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]

        if not any(eid in self.lights for eid in entity_ids):
            return

        if service == SERVICE_TURN_OFF:
            transition = service_data.get(ATTR_TRANSITION)
            _LOGGER.debug(
                "Detected an 'light.turn_off('%s', transition=%s)' event",
                entity_ids,
                transition,
            )
            for eid in entity_ids:
                self.turn_off_event[eid] = (event.context.id, transition)

        elif service == SERVICE_TURN_ON:
            _LOGGER.debug("Detected an 'light.turn_on('%s')' event", entity_ids)
            for eid in entity_ids:
                task = self.sleep_tasks.get(eid)
                if task is not None:
                    task.cancel()
                self.turn_on_event[eid] = event.context.id
