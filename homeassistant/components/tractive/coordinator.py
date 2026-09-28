"""Coordinator for the Tractive integration."""

from dataclasses import dataclass
import logging
from typing import Any, override

import aiotractive

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class TractiveCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for Tractive data."""

    config_entry: TractiveConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: aiotractive.Tractive,
        user_id: str,
        config_entry: TractiveConfigEntry,
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
        self.user_id = user_id

    @override
    async def _async_update_data(self) -> None:
        """No polling needed — data comes via push updates."""
        return

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator and register push update listener."""
        self.client.subscribe_updates(self._async_handle_update)

    @callback
    def _async_handle_update(self, error: Exception | None = None) -> None:
        """Handle updated data or connection errors from the Tractive API."""
        if error is not None:
            self.async_set_update_error(error)
            if isinstance(error, aiotractive.exceptions.UnauthorizedError):
                self.config_entry.async_start_reauth(self.hass)
        else:
            self.async_set_updated_data(None)

    async def async_start(self) -> None:
        """Start the background event listener."""
        await self.client.async_start_listener()

    @override
    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        await self.client.async_stop_listener()
        await self.client.close()
        await super().async_shutdown()


@dataclass
class Trackables:
    """A class that describes trackables."""

    tracker: aiotractive.tracker.Tracker
    trackable: dict[str, Any]
    tracker_details: dict[str, Any]
    hw_info: dict[str, Any]
    pos_report: dict[str, Any]
    health_overview: dict[str, Any]


@dataclass(slots=True)
class TractiveData:
    """Class for Tractive data."""

    coordinator: TractiveCoordinator
    trackables: list[Trackables]


type TractiveConfigEntry = ConfigEntry[TractiveData]
