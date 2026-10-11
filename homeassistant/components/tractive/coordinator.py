"""Coordinator for the Tractive integration."""

import logging
from typing import override

from aiotractive import Trackable, Tractive, TractiveStatus
from aiotractive.exceptions import TractiveError, UnauthorizedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

type TractiveConfigEntry = ConfigEntry[TractiveCoordinator]


class TractiveCoordinator(DataUpdateCoordinator[TractiveStatus]):
    """Coordinator for Tractive data."""

    config_entry: TractiveConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TractiveConfigEntry,
        client: Tractive,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Tractive",
            update_interval=None,
        )
        self.client = client
        self.trackables: list[Trackable] = []

    @override
    async def _async_setup(self) -> None:
        """Fetch the trackables and subscribe to push updates."""
        try:
            self.trackables = await self.client.async_fetch_trackables()
        except UnauthorizedError as error:
            raise ConfigEntryAuthFailed from error
        except TractiveError as error:
            raise UpdateFailed(error) from error
        self.client.subscribe_updates(self._async_handle_update)

    @override
    async def _async_update_data(self) -> TractiveStatus:
        """Fetch the current status via REST."""
        try:
            return await self.client.async_fetch_status()
        except UnauthorizedError as error:
            raise ConfigEntryAuthFailed from error
        except TractiveError as error:
            raise UpdateFailed(error) from error

    @callback
    def _async_handle_update(self, error: Exception | None) -> None:
        """Handle a push update or a channel error from the Tractive API."""
        if error is None:
            self.async_set_updated_data(self.client.status)
            return
        if isinstance(error, UnauthorizedError):
            self.config_entry.async_start_reauth(self.hass)
        self.async_set_update_error(error)
