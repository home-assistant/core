"""Coordinator for the Duosida EV Charger integration."""

from datetime import timedelta
import logging
from typing import override

from duosida_ev import (
    ChargerInfo,
    ChargerStatus,
    DuosidaClient,
    DuosidaError,
    DuosidaTimeoutError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# The charger pushes its status about every 10 s, and each push postpones the
# refresh. A refresh only runs when the pushes stop, to reconnect; the interval
# also spaces out reconnects, which the charger refuses when they come fast.
WATCHDOG_INTERVAL = timedelta(seconds=60)
# Two missed pushes, plus some slack.
STATUS_TIMEOUT = 25

type DuosidaConfigEntry = ConfigEntry[DuosidaCoordinator]


class DuosidaCoordinator(DataUpdateCoordinator[ChargerStatus]):
    """Keep one session with the charger and share the status it pushes."""

    config_entry: DuosidaConfigEntry
    info: ChargerInfo

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: DuosidaConfigEntry,
        client: DuosidaClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=WATCHDOG_INTERVAL,
        )
        self.client = client
        self._closing = False
        self._remove_listener = client.add_listener(self._handle_client_update)

    async def _async_close_session(self) -> None:
        """Close the session without reporting it as lost."""
        self._closing = True
        try:
            await self.client.disconnect()
        finally:
            self._closing = False

    def _update_failed(self, translation_key: str) -> UpdateFailed:
        """Return an update error that also spaces out the setup retries."""
        return UpdateFailed(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            retry_after=WATCHDOG_INTERVAL.total_seconds(),
        )

    @override
    async def _async_update_data(self) -> ChargerStatus:
        """Reconnect if the session dropped, and return a recent status."""
        try:
            # Returns at once while the session is open.
            info = await self.client.connect()
        except DuosidaError as err:
            raise self._update_failed("cannot_connect") from err
        if info.device_id != self.config_entry.unique_id:
            await self._async_close_session()
            raise self._update_failed("unexpected_device")
        self.info = info
        try:
            return await self.client.get_status(timeout=STATUS_TIMEOUT)
        except DuosidaTimeoutError as err:
            # The heartbeats can hold a session open after the status pushes
            # stopped; closing it lets the next refresh reconnect.
            await self._async_close_session()
            raise self._update_failed("no_status") from err
        except DuosidaError as err:
            raise self._update_failed("connection_lost") from err

    @callback
    def _handle_client_update(self) -> None:
        """Publish pushed status, and mark a dropped session unavailable.

        Until the first refresh succeeds, while the refresh fails, and for
        sessions it closes itself, the refresh reports the errors; it also
        logs the recovery. The client also notifies on connector changes,
        which bring no new status.
        """
        if self.data is None or not self.last_update_success or self._closing:
            return
        if not self.client.connected:
            self.async_set_update_error(self._update_failed("connection_lost"))
        elif (status := self.client.status) is not None and status is not self.data:
            self.async_set_updated_data(status)

    @override
    async def async_shutdown(self) -> None:
        """Stop the refreshes and close the session."""
        await super().async_shutdown()
        self._remove_listener()
        await self.client.disconnect()
