"""Component to embed nexia devices."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from nexia.home import NexiaHome

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_LOGGING_CHANGED
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

DEFAULT_UPDATE_RATE = 120


class NexiaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """DataUpdateCoordinator for nexia homes."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        nexia_home: NexiaHome,
    ) -> None:
        """Initialize DataUpdateCoordinator for the nexia home.

        This method must be run in the event loop.
        """
        self.nexia_home = nexia_home
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Nexia update",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_RATE),
            always_update=False,
        )
        self.cleanup_callbacks: list[CALLBACK_TYPE] = [
            hass.bus.async_listen(EVENT_LOGGING_CHANGED, self._async_handle_logging_changed)
        ]

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        return await self.nexia_home.update()

    @callback
    def async_cleanup(self) -> None:
        """Cleanup this instance.

        This method must be run in the event loop.
        """
        for cleanup_callback in self.cleanup_callbacks:
            cleanup_callback()

    @callback
    def _async_handle_logging_changed(self, _event: Event) -> None:
        """Handle when the logging level changes.

        Log responses if and only if enabled for debug logging.
        """
        self.nexia_home.log_response = _LOGGER.isEnabledFor(logging.DEBUG)
