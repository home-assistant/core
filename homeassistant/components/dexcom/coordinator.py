"""Coordinator for the Dexcom integration."""

from datetime import timedelta
import logging
from typing import override

from pydexcom import Dexcom, GlucoseReading

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_SCAN_INTERVAL = timedelta(seconds=180)
# Dexcom publishes a new reading every 5 minutes; allow some upload delay
_READING_INTERVAL = timedelta(minutes=5)
_UPLOAD_MARGIN = timedelta(seconds=20)
_MIN_INTERVAL = timedelta(seconds=30)

type DexcomConfigEntry = ConfigEntry[DexcomCoordinator]


class DexcomCoordinator(DataUpdateCoordinator[GlucoseReading | None]):
    """Dexcom Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: DexcomConfigEntry,
        dexcom: Dexcom,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=_SCAN_INTERVAL,
        )
        self.dexcom = dexcom
        self._unchanged_polls = 0

    @override
    async def _async_update_data(self) -> GlucoseReading | None:
        """Fetch data from API endpoint."""
        # Used if the fetch below fails, so an outage is not polled every 30 s
        self.update_interval = _SCAN_INTERVAL
        reading = await self.hass.async_add_executor_job(
            self.dexcom.get_current_glucose_reading
        )
        self.update_interval = self._next_interval(reading)
        return reading

    def _next_interval(self, reading: GlucoseReading | None) -> timedelta:
        """Return the delay until the next expected reading."""
        if reading is None:
            # No recent reading, the sensor may be offline
            self._unchanged_polls = 0
            return _SCAN_INTERVAL
        expected = reading.datetime + _READING_INTERVAL + _UPLOAD_MARGIN
        now = dt_util.utcnow()
        if (
            self.data is not None
            and reading.datetime == self.data.datetime
            and now >= expected
        ):
            # The next reading is late: retry once soon, then fall back
            self._unchanged_polls += 1
            return _MIN_INTERVAL if self._unchanged_polls == 1 else _SCAN_INTERVAL
        self._unchanged_polls = 0
        # Clamp in case the reading time is ahead of the local clock
        return min(
            max(expected - now, _MIN_INTERVAL),
            _READING_INTERVAL + _UPLOAD_MARGIN,
        )
