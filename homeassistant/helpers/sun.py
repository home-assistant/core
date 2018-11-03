"""Helpers for sun events."""
import datetime

from homeassistant.const import (
    SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET, SUN_EVENT_ASTRONOMICAL_DAWN,
    SUN_EVENT_ASTRONOMICAL_DUSK, SUN_EVENT_CIVIL_DAWN, SUN_EVENT_CIVIL_DUSK,
    SUN_EVENT_NAUTICAL_DAWN, SUN_EVENT_NAUTICAL_DUSK)
from homeassistant.core import callback
from homeassistant.util import dt as dt_util
from homeassistant.loader import bind_hass

DATA_LOCATION_CACHE = 'astral_location_cache'


@callback
@bind_hass
def get_astral_location(hass):
    """Get an astral location for the current Home Assistant configuration."""
    from astral import Location

    latitude = hass.config.latitude
    longitude = hass.config.longitude
    timezone = hass.config.time_zone.zone
    elevation = hass.config.elevation
    info = ('', '', latitude, longitude, timezone, elevation)

    # Cache astral locations so they aren't recreated with the same args
    if DATA_LOCATION_CACHE not in hass.data:
        hass.data[DATA_LOCATION_CACHE] = {}

    if info not in hass.data[DATA_LOCATION_CACHE]:
        hass.data[DATA_LOCATION_CACHE][info] = Location(info)

    return hass.data[DATA_LOCATION_CACHE][info]


@callback
@bind_hass
def get_astral_event_next(hass, event, utc_point_in_time=None,
                          offset=None, solar_depression=None):
    """Calculate the next specified solar event."""
    import astral

    location = get_astral_location(hass)

    if offset is None:
        offset = datetime.timedelta()

    if utc_point_in_time is None:
        utc_point_in_time = dt_util.utcnow()

    if solar_depression is None:
        solar_depression = 'civil'
    location.solar_depression = solar_depression

    mod = -1
    while True:
        try:
            next_dt = getattr(location, event)(
                dt_util.as_local(utc_point_in_time).date() +
                datetime.timedelta(days=mod),
                local=False) + offset
            if next_dt > utc_point_in_time:
                return next_dt
        except astral.AstralError:
            pass
        mod += 1


@callback
@bind_hass
def get_astral_event_date(hass, event, date=None, solar_depression=None):
    """Calculate the astral event time for the specified date."""
    import astral

    location = get_astral_location(hass)

    if date is None:
        date = dt_util.now().date()

    if isinstance(date, datetime.datetime):
        date = dt_util.as_local(date).date()

    if solar_depression is None:
        solar_depression = 'civil'
    location.solar_depression = solar_depression

    try:
        return getattr(location, event)(date, local=False)
    except astral.AstralError:
        # Event never occurs for specified date.
        return None


EVENT_TO_EVENT_DEPRESSION = {
    SUN_EVENT_SUNRISE: ('sunrise', None),
    SUN_EVENT_SUNSET: ('sunset', None),
    SUN_EVENT_ASTRONOMICAL_DAWN: ('dawn', 'astronomical'),
    SUN_EVENT_ASTRONOMICAL_DUSK: ('dusk', 'astronomical'),
    SUN_EVENT_CIVIL_DAWN: ('dawn', 'civil'),
    SUN_EVENT_CIVIL_DUSK: ('dusk', 'civil'),
    SUN_EVENT_NAUTICAL_DAWN: ('dawn', 'nautical'),
    SUN_EVENT_NAUTICAL_DUSK: ('dusk', 'nautical'),
    }


@callback
@bind_hass
def is_between(hass, from_, until, utc_point_in_time=None):
    """Calculate if the solar elevation is between 0°..-18°."""
    if utc_point_in_time is None:
        utc_point_in_time = dt_util.utcnow()

    from_event, from_dep = EVENT_TO_EVENT_DEPRESSION[from_]
    until_event, until_dep = EVENT_TO_EVENT_DEPRESSION[until]

    until_time = get_astral_event_next(
        hass, until_event, utc_point_in_time, solar_depression=until_dep)
    from_time = get_astral_event_next(
        hass, from_event, utc_point_in_time, solar_depression=from_dep)

    return until_time > from_time


@callback
@bind_hass
def is_up(hass, utc_point_in_time=None):
    """Calculate if the sun is currently up."""
    if utc_point_in_time is None:
        utc_point_in_time = dt_util.utcnow()

    next_sunrise = get_astral_event_next(hass, SUN_EVENT_SUNRISE,
                                         utc_point_in_time)
    next_sunset = get_astral_event_next(hass, SUN_EVENT_SUNSET,
                                        utc_point_in_time)

    return next_sunrise > next_sunset


@callback
@bind_hass
def is_night(hass, utc_point_in_time=None):
    """Return True if the solar elevation is -18° or less."""
    if utc_point_in_time is None:
        utc_point_in_time = dt_util.utcnow()

    next_astronomical_dusk = get_astral_event_next(
        hass, 'dusk', utc_point_in_time, solar_depression='astronomical')
    next_astronomical_dawn = get_astral_event_next(
        hass, 'dawn', utc_point_in_time, solar_depression='astronomical')

    return next_astronomical_dusk > next_astronomical_dawn


@callback
@bind_hass
def is_morning_twilight(hass, utc_point_in_time=None):
    """Return True if the solar elevation is between -18°..0°."""
    if utc_point_in_time is None:
        utc_point_in_time = dt_util.utcnow()

    next_astronomical_dawn = get_astral_event_next(
        hass, 'dawn', utc_point_in_time, solar_depression='astronomical')
    next_sunrise = get_astral_event_next(hass, 'sunrise', utc_point_in_time)

    return next_astronomical_dawn > next_sunrise


@callback
@bind_hass
def is_evening_twilight(hass, utc_point_in_time=None):
    """Return True if the solar elevation is between 0°..-18°."""
    if utc_point_in_time is None:
        utc_point_in_time = dt_util.utcnow()

    next_sunset = get_astral_event_next(hass, 'sunset', utc_point_in_time)
    next_astronomical_dusk = get_astral_event_next(
        hass, 'dusk', utc_point_in_time, solar_depression='astronomical')

    return next_sunset > next_astronomical_dusk
