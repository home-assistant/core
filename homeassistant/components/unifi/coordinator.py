"""UniFi Network data update coordinator."""

from datetime import timedelta
from typing import TYPE_CHECKING, override

from aiounifi.interfaces.api_handlers import APIHandler, ItemEvent

from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER

if TYPE_CHECKING:
    from .hub.hub import UnifiHub

POLL_INTERVAL = timedelta(seconds=10)


class UnifiDataUpdateCoordinator[HandlerT: APIHandler](DataUpdateCoordinator[None]):
    """Coordinator managing polling for a single UniFi API data source."""

    def __init__(
        self,
        hub: UnifiHub,
        handler: HandlerT,
    ) -> None:
        """Initialize coordinator."""
        supports_websocket = bool(handler.process_messages or handler.remove_messages)
        super().__init__(
            hub.hass,
            LOGGER,
            name=f"UniFi {type(handler).__name__}",
            config_entry=hub.config.entry,
            update_interval=None if supports_websocket else POLL_INTERVAL,
        )
        self._handler = handler

        hub.config.entry.async_on_unload(handler.subscribe(self._async_handle_update))

    @property
    def handler(self) -> HandlerT:
        """Return the aiounifi handler managed by this coordinator."""
        return self._handler

    @override
    async def _async_update_data(self) -> None:
        """Update data from the API handler."""
        await self._handler.update()

    @callback
    def _async_handle_update(self, event: ItemEvent, obj_id: str) -> None:
        """Notify listeners when the handler receives a websocket update."""
        self.async_set_updated_data(None)
