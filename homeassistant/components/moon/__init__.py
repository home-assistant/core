"""The Moon integration."""
from collections.abc import Iterable
import datetime
from typing import Any

from astral import moon

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    _LOGGER,
    PLATFORMS,
    STATE_FIRST_QUARTER,
    STATE_FULL_MOON,
    STATE_LAST_QUARTER,
    STATE_NEW_MOON,
    STATE_WANING_CRESCENT,
    STATE_WANING_GIBBOUS,
    STATE_WAXING_CRESCENT,
    STATE_WAXING_GIBBOUS,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def get_moon_phase(date: datetime.date) -> str:
    """Get moon phase."""
    state = moon.phase(date)

    if state < 0.5 or state > 27.5:
        return STATE_NEW_MOON
    if state < 6.5:
        return STATE_WAXING_CRESCENT
    if state < 7.5:
        return STATE_FIRST_QUARTER
    if state < 13.5:
        return STATE_WAXING_GIBBOUS
    if state < 14.5:
        return STATE_FULL_MOON
    if state < 20.5:
        return STATE_WANING_GIBBOUS
    if state < 21.5:
        return STATE_LAST_QUARTER
    return STATE_WANING_CRESCENT


def get_moon_phases(
    start_date: datetime.date, end_date: datetime.date | None = None
) -> list[dict[str, Any]]:
    """Get moon phases for a range of dates."""

    def generate_daterange(
        start_date: datetime.date, end_date: datetime.date | None = None
    ) -> Iterable[datetime.date]:
        """Generate a range of dates."""
        n_days = range(1)
        if end_date is not None and end_date > start_date:
            n_days = range(int((end_date - start_date).days))
        for n in n_days:
            yield start_date + datetime.timedelta(days=n)

    def start_date_moon_phase(
        current_date: datetime.date, current_phase: str
    ) -> datetime.date:
        """Get end date moon phase."""
        start_moon_phase: datetime.date | None = None
        for date_phase in generate_daterange(
            current_date - datetime.timedelta(days=8), current_date
        ):
            if (
                moon_phase := get_moon_phase(date_phase)
            ) is not None and moon_phase == current_phase:
                start_moon_phase = date_phase
                break
        if start_moon_phase is None:
            return current_date
        return start_moon_phase

    def end_date_moon_phase(
        current_date: datetime.date, current_phase: str
    ) -> datetime.date:
        """Get end date moon phase."""
        date_moon_phase: datetime.date | None = None
        for date_phase in generate_daterange(
            current_date, current_date + datetime.timedelta(days=28)
        ):
            if (
                moon_phase := get_moon_phase(date_phase)
            ) is not None and moon_phase != current_phase:
                date_moon_phase = date_phase
                break
        if date_moon_phase is None:
            return current_date
        return date_moon_phase

    moon_phases = []
    moon_phase_previous = None
    for date_phase in generate_daterange(start_date, end_date):
        moon_phase = None
        if (
            moon_phase := get_moon_phase(date_phase)
        ) is not None and moon_phase != moon_phase_previous:
            moon_phases.append(
                {
                    "date": start_date_moon_phase(date_phase, moon_phase),
                    "phase": moon_phase,
                    "end": end_date_moon_phase(date_phase, moon_phase),
                }
            )
            moon_phase_previous = moon_phase
    _LOGGER.debug(
        "Get moon phases: start=%s, end=%s, result=%s",
        start_date,
        end_date,
        moon_phases,
    )
    return moon_phases
