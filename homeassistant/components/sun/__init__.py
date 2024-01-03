"""Support for functionality to keep track of the sun."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from astral import SunDirection
from astral.location import Elevation, Location

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    EVENT_CORE_CONFIG_UPDATE,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, event
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.sun import (
    get_astral_location,
    get_location_astral_event_next,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    SIGNAL_DURATIONS_CHANGED,
    SIGNAL_EVENTS_CHANGED,
    SIGNAL_POSITION_CHANGED,
)

_LOGGER = logging.getLogger(__name__)

ENTITY_ID = "sun.sun"

STATE_ABOVE_HORIZON = "above_horizon"
STATE_BELOW_HORIZON = "below_horizon"

STATE_ATTR_AZIMUTH = "azimuth"
STATE_ATTR_ELEVATION = "elevation"
STATE_ATTR_RISING = "rising"
STATE_ATTR_NEXT_DAWN = "next_dawn"
STATE_ATTR_NEXT_DUSK = "next_dusk"
STATE_ATTR_NEXT_MIDNIGHT = "next_midnight"
STATE_ATTR_NEXT_NOON = "next_noon"
STATE_ATTR_NEXT_RISING = "next_rising"
STATE_ATTR_NEXT_SETTING = "next_setting"
STATE_ATTR_DAYLIGHT_DURATION = "daylight_duration"
STATE_ATTR_NIGHT_DURATION = "night_duration"
STATE_ATTR_TWILIGHT_SUNRISE_DURATION = "twilight_sunrise_duration"
STATE_ATTR_TWILIGHT_SUNSET_DURATION = "twilight_sunset_duration"

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


CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track the state of the sun."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    hass.data[DOMAIN] = Sun(hass)
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, [Platform.SENSOR]
    ):
        sun: Sun = hass.data.pop(DOMAIN)
        sun.remove_listeners()
        hass.states.async_remove(sun.entity_id)
    return unload_ok


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
            STATE_ATTR_DAYLIGHT_DURATION,
            STATE_ATTR_NIGHT_DURATION,
            STATE_ATTR_TWILIGHT_SUNRISE_DURATION,
            STATE_ATTR_TWILIGHT_SUNSET_DURATION,
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
    daylight_duration: timedelta
    night_duration: timedelta
    twilight_sunrise_duration: timedelta
    twilight_sunset_duration: timedelta
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
        self._update_durations_listener: CALLBACK_TYPE | None = None
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
        # The attributes need to be initialized before the first call to update_events() to avoid an AttributeError.
        self.daylight_duration = timedelta()
        self.night_duration = timedelta()
        self.twilight_sunrise_duration = timedelta()
        self.twilight_sunset_duration = timedelta()
        if self._update_events_listener:
            self._update_events_listener()
        self.update_events()
        if self._update_durations_listener:
            self._update_durations_listener()
        self.update_durations()

    @callback
    def remove_listeners(self) -> None:
        """Remove listeners."""
        if self._config_listener:
            self._config_listener()
        if self._update_events_listener:
            self._update_events_listener()
        if self._update_sun_position_listener:
            self._update_sun_position_listener()
        if self._update_durations_listener:
            self._update_durations_listener()

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
            STATE_ATTR_DAYLIGHT_DURATION: self.daylight_duration.total_seconds(),
            STATE_ATTR_NIGHT_DURATION: self.night_duration.total_seconds(),
            STATE_ATTR_TWILIGHT_SUNRISE_DURATION: self.twilight_sunrise_duration.total_seconds(),
            STATE_ATTR_TWILIGHT_SUNSET_DURATION: self.twilight_sunset_duration.total_seconds(),
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

    @callback
    def update_durations(self, now: datetime | None = None) -> None:
        """Calculate the dayligh, night, sunrise and sunset durations."""
        # First update sun position to assure the values are up-to-date.
        if self._update_sun_position_listener:
            self._update_sun_position_listener()
        self.update_sun_position()

        # Grab current time in case system clock changed since last time we ran.
        utc_point_in_time = dt_util.utcnow()
        try:
            start, end = self.location.daylight(
                dt_util.as_local(utc_point_in_time).date()
            )
            self.daylight_duration = end - start
        except ValueError:  # Catch Polar day / night / twilight.
            self.daylight_duration = (
                timedelta(days=1) if self.solar_elevation > -0.833 else timedelta()
            )
        try:
            start, end = self.location.night(dt_util.as_local(utc_point_in_time).date())
            self.night_duration = end - start
        except ValueError:  # Catch Polar day / night / twilight.
            self.night_duration = (
                timedelta(days=1) if self.solar_elevation <= -18.0 else timedelta()
            )
        try:
            start, end = self.location.twilight(
                dt_util.as_local(utc_point_in_time).date(), SunDirection.RISING
            )
            self.twilight_sunrise_duration = end - start
        except ValueError:  # Catch Polar day / night / twilight.
            self.twilight_sunrise_duration = (
                timedelta(hours=12)
                if self.solar_elevation > -6.0 and self.solar_elevation <= -0.833
                else timedelta()
            )
        try:
            start, end = self.location.twilight(
                dt_util.as_local(utc_point_in_time).date(), SunDirection.SETTING
            )
            self.twilight_sunset_duration = end - start
        except ValueError:  # Catch Polar day / night / twilight.
            self.twilight_sunset_duration = (
                timedelta(hours=12)
                if self.solar_elevation > -6.0 and self.solar_elevation <= -0.833
                else timedelta()
            )

        _LOGGER.debug(
            "sun duarations_update@%s: daylight_duration=%s night_duration=%s twilight_sunrise_duration=%s twilight_sunset_duration=%s",
            utc_point_in_time.isoformat(),
            self.daylight_duration.total_seconds(),
            self.night_duration.total_seconds(),
            self.twilight_sunrise_duration.total_seconds(),
            self.twilight_sunset_duration.total_seconds(),
        )
        self.async_write_ha_state()

        async_dispatcher_send(self.hass, SIGNAL_DURATIONS_CHANGED)

        # Next update will occur on the beginning of the next day.
        delta = timedelta(
            seconds=(
                (
                    (24 - dt_util.as_local(utc_point_in_time).hour) * 60
                    - dt_util.as_local(utc_point_in_time).minute
                )
                * 60
                - dt_util.as_local(utc_point_in_time).second
            )
        )
        self._update_durations_listener = event.async_track_point_in_utc_time(
            self.hass, self.update_durations, utc_point_in_time + delta
        )
