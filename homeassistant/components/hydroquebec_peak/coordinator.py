"""DataUpdateCoordinator for the Hydro-Québec Peak Events integration."""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import override

from hydropeak_opendata import OpenDataClient, OpenDataError, PeakEvent

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_OFFER, DOMAIN, LOGGER, SCAN_INTERVAL

type HydroQuebecPeakConfigEntry = ConfigEntry[HydroQuebecPeakCoordinator]


class HydroQuebecPeakCoordinator(DataUpdateCoordinator[tuple[PeakEvent, ...]]):
    """Coordinator fetching peak events for one offer.

    Each config entry (one per offer) has its own coordinator. The library
    client sends conditional requests, so refreshes are answered with a
    cheap 304 unless Hydro-Québec published new data.
    """

    config_entry: HydroQuebecPeakConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: HydroQuebecPeakConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.offer: str = config_entry.data[CONF_OFFER]
        self.client = OpenDataClient(async_get_clientsession(hass))
        self._boundary_unsub: Callable[[], None] | None = None

    @override
    async def _async_update_data(self) -> tuple[PeakEvent, ...]:
        """Fetch the events for this entry's offer."""
        try:
            events = await self.client.get_events(self.offer)
        except OpenDataError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self._schedule_boundary_refresh(events)
        return events

    def _schedule_boundary_refresh(self, events: tuple[PeakEvent, ...]) -> None:
        """Notify entities at the next moment a state can flip.

        Entity states depend on the current time (event in progress,
        today/tomorrow flags), not only on the fetched data. Schedule a
        listener update at the next event start/end or local midnight so
        states flip on time instead of waiting for the next poll.
        """
        now = dt_util.utcnow()
        boundaries = [
            boundary
            for event in events
            for boundary in (event.start, event.end)
            if boundary > now
        ]
        boundaries.append(dt_util.start_of_local_day() + timedelta(days=1))

        if self._boundary_unsub is not None:
            self._boundary_unsub()
        self._boundary_unsub = async_track_point_in_utc_time(
            self.hass, self._handle_boundary, min(boundaries)
        )

    @callback
    def _handle_boundary(self, now: datetime) -> None:
        """Handle a state boundary: refresh listeners and rearm."""
        self._boundary_unsub = None
        self._schedule_boundary_refresh(self.data or ())
        self.async_update_listeners()

    @override
    async def async_shutdown(self) -> None:
        """Cancel the boundary timer on shutdown."""
        await super().async_shutdown()
        if self._boundary_unsub is not None:
            self._boundary_unsub()
            self._boundary_unsub = None
