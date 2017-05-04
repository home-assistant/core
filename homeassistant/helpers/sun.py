"""Helpers for sun events."""
from datetime import timedelta

from homeassistant.core import callback
from homeassistant.util import dt as dt_util


# Cache astral locations so they aren't recreated with the same args
_LOCATION_CACHE = {}


@callback
def get_astral_location(hass):
    """Get an astral location for the current hass configuration."""
    from astral import Location

    latitude = hass.config.latitude
    longitude = hass.config.longitude
    timezone = hass.config.time_zone.zone
    elevation = hass.config.elevation
    info = ('', '', latitude, longitude, timezone, elevation)

    if info not in _LOCATION_CACHE:
        _LOCATION_CACHE[info] = Location(info)

    return _LOCATION_CACHE[info]


@callback
def get_astral_event_next(hass, event, utc_point_in_time=None, offset=None):
    """Calculate the next specified solar event."""
    import astral

    location = get_astral_location(hass)

    if offset is None:
        offset = timedelta()

    if utc_point_in_time is None:
        utc_point_in_time = dt_util.utcnow()

    mod = -1
    while True:
        try:
            next_dt = getattr(location, event)(
                dt_util.as_local(utc_point_in_time).date() +
                timedelta(days=mod),
                local=False) + offset
            if next_dt > utc_point_in_time:
                return next_dt
        except astral.AstralError:
            pass
        mod += 1


@callback
def get_astral_event_date(hass, event, now=None):
    """Calculate the astral event time for the specified date."""
    import astral

    location = get_astral_location(hass)

    if now is None:
        now = dt_util.now()

    try:
        return getattr(location, event)(now.date(), local=False)
    except astral.AstralError:
        # Event never occurs for specified date.
        return None


@callback
def is_up(hass, utc_point_in_time=None):
    """Calculate if the sun is currently up."""
    if utc_point_in_time is None:
        utc_point_in_time = dt_util.utcnow()

    next_sunrise = get_astral_event_next(hass, 'sunrise', utc_point_in_time)
    next_sunset = get_astral_event_next(hass, 'sunset', utc_point_in_time)

    return next_sunrise > next_sunset
