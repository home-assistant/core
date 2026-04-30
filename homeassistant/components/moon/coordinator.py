"""Coordinate moon calculations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from math import degrees
from typing import cast

from astral import moon as astral_moon
import ephem

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.sun import get_astral_location
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    STATE_FIRST_QUARTER,
    STATE_FULL_MOON,
    STATE_LAST_QUARTER,
    STATE_NEW_MOON,
    STATE_WANING_CRESCENT,
    STATE_WANING_GIBBOUS,
    STATE_WAXING_CRESCENT,
    STATE_WAXING_GIBBOUS,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


@dataclass(kw_only=True, frozen=True)
class MoonData:
    """Calculated moon data."""

    above_horizon: bool
    phase: str
    illumination: float
    elevation: float
    azimuth: float
    next_rising: datetime | None
    next_setting: datetime | None
    next_transit: datetime
    next_new_moon: datetime
    next_first_quarter_moon: datetime
    next_full_moon: datetime
    next_last_quarter_moon: datetime


class MoonUpdateCoordinator(DataUpdateCoordinator[MoonData]):
    """Coordinate moon calculations."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> MoonData:
        """Fetch updated moon data."""
        now = dt_util.utcnow()
        local_date = dt_util.as_local(now).date()
        location, elevation = get_astral_location(self.hass)

        return await self.hass.async_add_executor_job(
            _get_moon_data,
            now,
            local_date,
            location.latitude,
            location.longitude,
            elevation if isinstance(elevation, (int, float)) else 0,
        )


def moon_phase_state(value: float) -> str:
    """Convert Astral's moon phase value to the sensor state."""
    if value < 0.5 or value > 27.5:
        return STATE_NEW_MOON
    if value < 6.5:
        return STATE_WAXING_CRESCENT
    if value < 7.5:
        return STATE_FIRST_QUARTER
    if value < 13.5:
        return STATE_WAXING_GIBBOUS
    if value < 14.5:
        return STATE_FULL_MOON
    if value < 20.5:
        return STATE_WANING_GIBBOUS
    if value < 21.5:
        return STATE_LAST_QUARTER
    return STATE_WANING_CRESCENT


def ephem_date_to_datetime(value: ephem.Date) -> datetime:
    """Convert an ephem date to a UTC datetime."""
    return cast(datetime, value.datetime().replace(tzinfo=dt_util.UTC))


def _get_next_event(
    observer: ephem.Observer, event: Callable[[ephem.Moon], ephem.Date]
) -> datetime | None:
    """Safely fetch the next moon event."""
    try:
        return ephem_date_to_datetime(event(ephem.Moon()))
    except ephem.AlwaysUpError, ephem.NeverUpError:
        return None


def _get_moon_data(
    now: datetime,
    local_date: date,
    latitude: float,
    longitude: float,
    elevation: float,
) -> MoonData:
    """Calculate moon data for the configured location."""
    observer = ephem.Observer()
    observer.lat = str(latitude)
    observer.lon = str(longitude)
    observer.elevation = elevation
    observer.date = now

    current_moon = ephem.Moon(observer)

    return MoonData(
        above_horizon=float(current_moon.alt) > 0,
        phase=moon_phase_state(astral_moon.phase(local_date)),
        illumination=round(current_moon.phase, 1),
        elevation=round(degrees(float(current_moon.alt)), 2),
        azimuth=round(degrees(float(current_moon.az)), 2),
        next_rising=_get_next_event(observer, observer.next_rising),
        next_setting=_get_next_event(observer, observer.next_setting),
        next_transit=ephem_date_to_datetime(observer.next_transit(ephem.Moon())),
        next_new_moon=ephem_date_to_datetime(ephem.next_new_moon(observer.date)),
        next_first_quarter_moon=ephem_date_to_datetime(
            ephem.next_first_quarter_moon(observer.date)
        ),
        next_full_moon=ephem_date_to_datetime(ephem.next_full_moon(observer.date)),
        next_last_quarter_moon=ephem_date_to_datetime(
            ephem.next_last_quarter_moon(observer.date)
        ),
    )
