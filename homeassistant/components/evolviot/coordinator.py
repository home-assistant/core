"""Data coordinator for EvolvIOT."""

import logging
from typing import override

from pyevolviot import (
    EvolvIOTApi,
    EvolvIOTData,
    EvolvIOTEntity,
    EvolvIOTEvent,
    EvolvIOTReadyEvent,
    EvolvIOTState,
    EvolvIOTStateChangedEvent,
    EvolvIOTWebSocket,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EvolvIOTDataUpdateCoordinator(DataUpdateCoordinator[EvolvIOTData]):
    """Coordinate EvolvIOT WebSocket data."""

    def __init__(
        self, hass: HomeAssistant, api: EvolvIOTApi, entry: ConfigEntry
    ) -> None:
        """Initialize the data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,
        )
        self.api = api
        self.websocket: EvolvIOTWebSocket | None = None

    async def async_setup(self) -> None:
        """Connect the EvolvIOT WebSocket and load initial data."""
        self.websocket = await self.api.async_connect_websocket()
        entry = self.config_entry
        assert entry is not None
        entry.async_on_unload(
            self.websocket.async_add_listener(self._async_handle_event)
        )
        self.async_set_updated_data(self.websocket.data)
        entry.async_create_background_task(
            self.hass,
            self.websocket.async_run_forever(),
            f"{DOMAIN}-websocket",
        )

    @override
    async def async_shutdown(self) -> None:
        """Close the WebSocket connection."""
        if self.websocket is not None:
            await self.websocket.async_close()
            self.websocket = None
        await super().async_shutdown()

    @property
    def entities(self) -> dict[str, EvolvIOTEntity]:
        """Return entities keyed by backend entity id."""
        return self.data.entities if self.data is not None else {}

    @property
    def states(self) -> dict[str, EvolvIOTState]:
        """Return states keyed by backend entity id."""
        return self.data.states if self.data is not None else {}

    async def async_command(self, entity_id: str, command: str) -> None:
        """Send a command to an EvolvIOT entity."""
        if self.websocket is None or not self.websocket.connected:
            await self.api.async_send_command(entity_id, command)
            return

        await self.websocket.async_command(entity_id, command)

    @override
    async def _async_update_data(self) -> EvolvIOTData:
        """Refresh data over the WebSocket."""
        if self.websocket is None:
            return self.data or EvolvIOTData(user_id="", entities={}, states={})
        return await self.websocket.async_refresh()

    async def _async_handle_event(self, event: EvolvIOTEvent) -> None:
        """Handle an EvolvIOT WebSocket event."""
        match event:
            case EvolvIOTReadyEvent(data):
                self.async_set_updated_data(data)
            case EvolvIOTStateChangedEvent(state) if self.data is not None:
                self.async_set_updated_data(self.data.with_state(state))
