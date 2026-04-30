"""Coordinate moon calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from astral import moon as astral_moon

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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

    phase: str


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
        local_date = dt_util.as_local(dt_util.utcnow()).date()
        return MoonData(phase=moon_phase_state(astral_moon.phase(local_date)))


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
