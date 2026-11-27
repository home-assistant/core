"""Class representing a Devialet update coordinator."""

from datetime import timedelta
import logging
from typing import override

from devialet import DevialetApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)
PUSH_SCAN_INTERVAL = timedelta(minutes=1)

type DevialetConfigEntry = ConfigEntry[DevialetCoordinator]


class DevialetCoordinator(DataUpdateCoordinator[None]):
    """Devialet update coordinator."""

    config_entry: DevialetConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: DevialetConfigEntry, client: DevialetApi
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        await self.client.async_update()

        if await self.client.async_search_allowed():
            self.config_entry.async_create_background_task(
                self.hass,
                self.client.async_discover_upnp_device(),
                f"{DOMAIN}_upnp_discovery",
            )

    async def async_listen(self) -> None:
        """Keep the data up to date with push notifications."""
        await self.client.async_listen(
            self._async_handle_push_update, self._async_handle_connection_change
        )

    @callback
    def _async_handle_push_update(self) -> None:
        """Handle a push update from the device."""
        # Keep the poll schedule, the poll also starts the UPnP discovery
        self.async_update_listeners()

    @callback
    def _async_handle_connection_change(self, connected: bool) -> None:
        """Poll less often while push notifications are received."""
        self.update_interval = PUSH_SCAN_INTERVAL if connected else SCAN_INTERVAL
        if not connected:
            # Check availability right away instead of waiting for the slow poll
            self.config_entry.async_create_task(self.hass, self.async_request_refresh())
