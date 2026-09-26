"""Coordinate Axle event updates."""

from datetime import datetime
import logging
from typing import override

from aioaxlevpp import AxleAuthenticationError, AxleClient, AxleError, GridEvent

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)
type AxleConfigEntry = ConfigEntry[AxleCoordinator]


class AxleCoordinator(DataUpdateCoordinator[GridEvent | None]):
    """Fetch one event using the provider's documented polling interval."""

    config_entry: AxleConfigEntry
    _unsub_event_update: CALLBACK_TYPE | None = None

    def __init__(
        self, hass: HomeAssistant, entry: AxleConfigEntry, client: AxleClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.client = client

    @callback
    def _cancel_event_update(self) -> None:
        """Cancel the scheduled event boundary."""
        if self._unsub_event_update is not None:
            self._unsub_event_update()
            self._unsub_event_update = None

    @callback
    def _schedule_event_update(self) -> None:
        """Schedule the next boundary without an additional API request."""
        self._cancel_event_update()
        if (
            self._shutdown_requested
            or not self.last_update_success
            or self.data is None
        ):
            return
        now = dt_util.utcnow()
        for boundary in (self.data.start, self.data.end):
            if boundary > now:
                self._unsub_event_update = async_track_point_in_utc_time(
                    self.hass, self._handle_event_update, boundary
                )
                return

    @callback
    def _handle_event_update(self, now: datetime) -> None:
        """Notify entities when an event starts or ends."""
        self._unsub_event_update = None
        self._schedule_event_update()
        self.async_update_listeners()

    @callback
    @override
    def _async_refresh_finished(self) -> None:
        """Update the boundary timer after fetching the event."""
        self._schedule_event_update()

    @override
    async def async_shutdown(self) -> None:
        """Cancel event updates when the coordinator shuts down."""
        await super().async_shutdown()
        self._cancel_event_update()

    @override
    async def _async_update_data(self) -> GridEvent | None:
        """Fetch the event without confusing outages with an empty schedule."""
        try:
            event = await self.client.get_event()
        except AxleAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="authentication_failed"
            ) from err
        except AxleError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        return None if event is not None and event.opted_out else event
