"""Support for functionality to keep track of the sun."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from astral.location import Elevation, Location

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_CORE_CONFIG_UPDATE,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import event
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.sun import (
    get_astral_location,
    get_location_astral_event_next,
)
from homeassistant.util import dt as dt_util

from .const import (
    SIGNAL_EVENTS_CHANGED,
    SIGNAL_POSITION_CHANGED,
    STATE_ABOVE_HORIZON,
    STATE_BELOW_HORIZON,
)

type SunConfigEntry = ConfigEntry[Sun]

_LOGGER = logging.getLogger(__name__)

ENTITY_ID = "sun.sun"

STATE_ATTR_AZIMUTH = "azimuth"
STATE_ATTR_ELEVATION = "elevation"
STATE_ATTR_RISING = "rising"
STATE_ATTR_NEXT_DAWN = "next_dawn"
STATE_ATTR_NEXT_DUSK = "next_dusk"
STATE_ATTR_NEXT_MIDNIGHT = "next_midnight"
STATE_ATTR_NEXT_NOON = "next_noon"
STATE_ATTR_NEXT_RISING = "next_rising"
STATE_ATTR_NEXT_SETTING = "next_setting"

# The algorithm used here is somewhat complicated. It aims to cut down
# the number of sensor updates over the day. It's documented best in
# the PR for the change, see the Discussion section of:
# https://github.com/home-assistant/core/pull/23832


# As documented in wikipedia: https://en.wikipedia.org/wiki/Twilight
# sun is:
# < -18° of horizon - all stars visible
PHASE_NIGHT = "night"
# 18°-12° - some stars not visible
PHASE_ASTRONOMICAL_TWILIGHT = "astronomical_twilight"
# 12°-6° - horizon visible
PHASE_NAUTICAL_TWILIGHT = "nautical_twilight"
# 6°-0° - objects visible
PHASE_TWILIGHT = "twilight"
# 0°-10° above horizon, sun low on horizon
PHASE_SMALL_DAY = "small_day"
# > 10° above horizon
PHASE_DAY = "day"

# 4 mins is one degree of arc change of the sun on its circle.
# During the night and the middle of the day we don't update
# that much since it's not important.
_PHASE_UPDATES = {
    PHASE_NIGHT: timedelta(minutes=4 * 5),
    PHASE_ASTRONOMICAL_TWILIGHT: timedelta(minutes=4 * 2),
    PHASE_NAUTICAL_TWILIGHT: timedelta(minutes=4 * 2),
    PHASE_TWILIGHT: timedelta(minutes=4),
    PHASE_SMALL_DAY: timedelta(minutes=2),
    PHASE_DAY: timedelta(minutes=4),
}


class Sun(Entity):
    """Representation of the Sun."""

    _unrecorded_attributes = frozenset(
        {
            STATE_ATTR_AZIMUTH,
            STATE_ATTR_ELEVATION,
            STATE_ATTR_RISING,
            STATE_ATTR_NEXT_DAWN,
            STATE_ATTR_NEXT_DUSK,
            STATE_ATTR_NEXT_MIDNIGHT,
            STATE_ATTR_NEXT_NOON,
            STATE_ATTR_NEXT_RISING,
            STATE_ATTR_NEXT_SETTING,
        }
    )

    _attr_name = "Sun"
    entity_id = ENTITY_ID
    # This entity is legacy and does not have a platform.
    # We can't fix this easily without breaking changes.
    _no_platform_reported = True

    location: Location
    elevation: Elevation
    next_rising: datetime
    next_setting: datetime
    next_dawn: datetime
    next_dusk: datetime
    next_midnight: datetime
    next_noon: datetime
    solar_elevation: float
    solar_azimuth: float
    rising: bool
    _next_change: datetime

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the sun."""
        self.hass = hass
        self.phase: str | None = None

        # This is normally done by async_internal_added_to_hass which is not called
        # for sun because sun has no platform
        self._state_info = {
            "unrecorded_attributes": self._Entity__combined_unrecorded_attributes  # type: ignore[attr-defined]
        }

        self._config_listener: CALLBACK_TYPE | None = None
        self._update_events_listener: CALLBACK_TYPE | None = None
        self._update_sun_position_listener: CALLBACK_TYPE | None = None
        self._config_listener = self.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, self.update_location
        )
        self.update_location(initial=True)

    @callback
    def update_location(self, _: Event | None = None, initial: bool = False) -> None:
        """Update location."""
        location, elevation = get_astral_location(self.hass)
        if not initial and location == self.location:
            return
        self.location = location
        self.elevation = elevation
        if self._update_events_listener:
            self._update_events_listener()
        self.update_events()

    @callback
    def remove_listeners(self) -> None:
        """Remove listeners."""
        if self._config_listener:
            self._config_listener()
        if self._update_events_listener:
            self._update_events_listener()
        if self._update_sun_position_listener:
            self._update_sun_position_listener()

    @property
    def state(self) -> str:
        """Return the state of the sun."""
        # 0.8333 is the same value as astral uses
        if self.solar_elevation > -0.833:
            return STATE_ABOVE_HORIZON

        return STATE_BELOW_HORIZON

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the sun."""
        return {
            STATE_ATTR_NEXT_DAWN: self.next_dawn.isoformat(),
            STATE_ATTR_NEXT_DUSK: self.next_dusk.isoformat(),
            STATE_ATTR_NEXT_MIDNIGHT: self.next_midnight.isoformat(),
            STATE_ATTR_NEXT_NOON: self.next_noon.isoformat(),
            STATE_ATTR_NEXT_RISING: self.next_rising.isoformat(),
            STATE_ATTR_NEXT_SETTING: self.next_setting.isoformat(),
            STATE_ATTR_ELEVATION: self.solar_elevation,
            STATE_ATTR_AZIMUTH: self.solar_azimuth,
            STATE_ATTR_RISING: self.rising,
        }

    def _check_event(
        self, utc_point_in_time: datetime, sun_event: str, before: str | None
    ) -> datetime:
        next_utc = get_location_astral_event_next(
            self.location, self.elevation, sun_event, utc_point_in_time
        )
        if next_utc < self._next_change:
            self._next_change = next_utc
            self.phase = before
        return next_utc

    @callback
    def update_events(self, now: datetime | None = None) -> None:
        """Update the attributes containing solar events."""
        # Grab current time in case system clock changed since last time we ran.
        utc_point_in_time = dt_util.utcnow()
        self._next_change = utc_point_in_time + timedelta(days=400)

        # Work our way around the solar cycle, figure out the next
        # phase. Some of these are stored.
        self.location.solar_depression = "astronomical"
        self._check_event(utc_point_in_time, "dawn", PHASE_NIGHT)
        self.location.solar_depression = "nautical"
        self._check_event(utc_point_in_time, "dawn", PHASE_ASTRONOMICAL_TWILIGHT)
        self.location.solar_depression = "civil"
        self.next_dawn = self._check_event(
            utc_point_in_time, "dawn", PHASE_NAUTICAL_TWILIGHT
        )
        self.next_rising = self._check_event(
            utc_point_in_time, SUN_EVENT_SUNRISE, PHASE_TWILIGHT
        )
        self.location.solar_depression = -10
        self._check_event(utc_point_in_time, "dawn", PHASE_SMALL_DAY)
        self.next_noon = self._check_event(utc_point_in_time, "noon", None)
        self._check_event(utc_point_in_time, "dusk", PHASE_DAY)
        self.next_setting = self._check_event(
            utc_point_in_time, SUN_EVENT_SUNSET, PHASE_SMALL_DAY
        )
        self.location.solar_depression = "civil"
        self.next_dusk = self._check_event(utc_point_in_time, "dusk", PHASE_TWILIGHT)
        self.location.solar_depression = "nautical"
        self._check_event(utc_point_in_time, "dusk", PHASE_NAUTICAL_TWILIGHT)
        self.location.solar_depression = "astronomical"
        self._check_event(utc_point_in_time, "dusk", PHASE_ASTRONOMICAL_TWILIGHT)
        self.next_midnight = self._check_event(utc_point_in_time, "midnight", None)
        self.location.solar_depression = "civil"

        # if the event was solar midday or midnight, phase will now
        # be None. Solar noon doesn't always happen when the sun is
        # even in the day at the poles, so we can't rely on it.
        # Need to calculate phase if next is noon or midnight
        if self.phase is None:
            elevation = self.location.solar_elevation(self._next_change, self.elevation)
            if elevation >= 10:
                self.phase = PHASE_DAY
            elif elevation >= 0:
                self.phase = PHASE_SMALL_DAY
            elif elevation >= -6:
                self.phase = PHASE_TWILIGHT
            elif elevation >= -12:
                self.phase = PHASE_NAUTICAL_TWILIGHT
            elif elevation >= -18:
                self.phase = PHASE_ASTRONOMICAL_TWILIGHT
            else:
                self.phase = PHASE_NIGHT

        self.rising = self.next_noon < self.next_midnight

        _LOGGER.debug(
            "sun phase_update@%s: phase=%s", utc_point_in_time.isoformat(), self.phase
        )
        if self._update_sun_position_listener:
            self._update_sun_position_listener()
        self.update_sun_position()
        async_dispatcher_send(self.hass, SIGNAL_EVENTS_CHANGED)

        # Set timer for the next solar event
        self._update_events_listener = event.async_track_point_in_utc_time(
            self.hass, self.update_events, self._next_change
        )
        _LOGGER.debug("next time: %s", self._next_change.isoformat())

    @callback
    def update_sun_position(self, now: datetime | None = None) -> None:
        """Calculate the position of the sun."""
        # Grab current time in case system clock changed since last time we ran.
        utc_point_in_time = dt_util.utcnow()
        self.solar_azimuth = round(
            self.location.solar_azimuth(utc_point_in_time, self.elevation), 2
        )
        self.solar_elevation = round(
            self.location.solar_elevation(utc_point_in_time, self.elevation), 2
        )

        _LOGGER.debug(
            "sun position_update@%s: elevation=%s azimuth=%s",
            utc_point_in_time.isoformat(),
            self.solar_elevation,
            self.solar_azimuth,
        )
        self.async_write_ha_state()

        async_dispatcher_send(self.hass, SIGNAL_POSITION_CHANGED)

        # Next update as per the current phase
        assert self.phase
        delta = _PHASE_UPDATES[self.phase]
        # if the next update is within 1.25 of the next
        # position update just drop it
        if utc_point_in_time + delta * 1.25 > self._next_change:
            self._update_sun_position_listener = None
            return
        self._update_sun_position_listener = event.async_track_point_in_utc_time(
            self.hass, self.update_sun_position, utc_point_in_time + delta
        )
