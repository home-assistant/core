"""Helpers for sun events."""
import datetime

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
def get_astral_event_next(hass, event, utc_point_in_time=None, offset=None):
    """Calculate the next specified solar event."""
    import astral

    location = get_astral_location(hass)

    if offset is None:
        offset = datetime.timedelta()

    if utc_point_in_time is None:
        utc_point_in_time = dt_util.utcnow()

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
def get_astral_event_date(hass, event, date=None):
    """Calculate the astral event time for the specified date."""
    import astral

    location = get_astral_location(hass)

    if date is None:
        date = dt_util.now().date()

    if isinstance(date, datetime.datetime):
        date = dt_util.as_local(date).date()

    try:
        return getattr(location, event)(date, local=False)
    except astral.AstralError:
        # Event never occurs for specified date.
        return None


@callback
@bind_hass
def is_up(hass, utc_point_in_time=None):
    """Calculate if the sun is currently up."""
    if utc_point_in_time is None:
        utc_point_in_time = dt_util.utcnow()

    next_sunrise = get_astral_event_next(hass, 'sunrise', utc_point_in_time)
    next_sunset = get_astral_event_next(hass, 'sunset', utc_point_in_time)

    return next_sunrise > next_sunset
