"""Helpers for sun events."""

from collections.abc import Callable
import datetime
from typing import TYPE_CHECKING, Any, cast

from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .deprecation import deprecated_function

if TYPE_CHECKING:
    import astral
    import astral.location

type _AstralSunEventCallable = Callable[..., datetime.datetime]


@deprecated_function(
    "homeassistant.helpers.sun.get_astral_observer",
    breaks_in_ha_version="2027.7",
)
@callback
def get_astral_location(
    hass: HomeAssistant,
) -> tuple[astral.location.Location, astral.Elevation]:
    """Get an astral location for the current Home Assistant configuration."""
    from astral import LocationInfo  # noqa: PLC0415
    from astral.location import Location  # noqa: PLC0415

    latitude = hass.config.latitude
    longitude = hass.config.longitude
    timezone = str(hass.config.time_zone)
    elevation = hass.config.elevation

    return Location(LocationInfo("", "", timezone, latitude, longitude)), elevation


@callback
def get_astral_observer(hass: HomeAssistant) -> astral.Observer:
    """Get an astral observer for the current Home Assistant configuration."""
    from astral import Observer  # noqa: PLC0415

    return Observer(hass.config.latitude, hass.config.longitude, hass.config.elevation)


@callback
def get_astral_event_next(
    hass: HomeAssistant,
    event: str,
    utc_point_in_time: datetime.datetime | None = None,
    offset: datetime.timedelta | None = None,
) -> datetime.datetime:
    """Calculate the next specified solar event."""
    observer = get_astral_observer(hass)
    return get_observer_astral_event_next(observer, event, utc_point_in_time, offset)


@deprecated_function(
    "homeassistant.helpers.sun.get_observer_astral_event_next",
    breaks_in_ha_version="2027.7",
)
@callback
def get_location_astral_event_next(
    location: astral.location.Location,
    elevation: astral.Elevation,
    event: str,
    utc_point_in_time: datetime.datetime | None = None,
    offset: datetime.timedelta | None = None,
) -> datetime.datetime:
    """Calculate the next specified solar event."""
    from astral import Observer  # noqa: PLC0415

    observer = Observer(location.latitude, location.longitude, elevation)
    depression = location.solar_depression if event in ("dawn", "dusk") else None
    return get_observer_astral_event_next(
        observer, event, utc_point_in_time, offset, depression
    )


@callback
def get_observer_astral_event_next(
    observer: astral.Observer,
    event: str,
    utc_point_in_time: datetime.datetime | None = None,
    offset: datetime.timedelta | None = None,
    depression: float | None = None,
) -> datetime.datetime:
    """Calculate the next specified solar event."""
    import astral.sun  # noqa: PLC0415

    if offset is None:
        offset = datetime.timedelta()

    if utc_point_in_time is None:
        utc_point_in_time = dt_util.utcnow()

    event_func = cast(_AstralSunEventCallable, getattr(astral.sun, event))
    kwargs: dict[str, Any] = {}
    if depression is not None:
        kwargs["depression"] = depression

    mod = -1
    first_err = None
    while mod < 367:
        try:
            next_dt = (
                event_func(
                    observer,
                    dt_util.as_local(utc_point_in_time).date()
                    + datetime.timedelta(days=mod),
                    **kwargs,
                )
                + offset
            )
            if next_dt > utc_point_in_time:
                return next_dt
        except ValueError as err:
            if not first_err:
                first_err = err
        mod += 1
    raise ValueError(
        f"Unable to find event after one year, initial ValueError: {first_err}"
    ) from first_err


@callback
def get_astral_event_date(
    hass: HomeAssistant,
    event: str,
    date: datetime.date | datetime.datetime | None = None,
) -> datetime.datetime | None:
    """Calculate the astral event time for the specified date."""
    import astral.sun  # noqa: PLC0415

    observer = get_astral_observer(hass)

    if date is None:
        date = dt_util.now().date()

    if isinstance(date, datetime.datetime):
        date = dt_util.as_local(date).date()

    event_func = cast(_AstralSunEventCallable, getattr(astral.sun, event))
    try:
        return event_func(observer, date)
    except ValueError:
        # Event never occurs for specified date.
        return None


@callback
def is_up(
    hass: HomeAssistant, utc_point_in_time: datetime.datetime | None = None
) -> bool:
    """Calculate if the sun is currently up."""
    if utc_point_in_time is None:
        utc_point_in_time = dt_util.utcnow()

    next_sunrise = get_astral_event_next(hass, SUN_EVENT_SUNRISE, utc_point_in_time)
    next_sunset = get_astral_event_next(hass, SUN_EVENT_SUNSET, utc_point_in_time)

    return next_sunrise > next_sunset
