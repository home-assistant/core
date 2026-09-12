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


class UnifiDataUpdateCoordinator[HandlerT: APIHandler](
    DataUpdateCoordinator[tuple[ItemEvent, str] | None]
):
    """Coordinator managing websocket or polling updates for a UniFi API handler."""

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
        """Notify listeners which object changed on a websocket update."""
        self.async_set_updated_data((event, obj_id))

    @callback
    @override
    def async_update_listeners(self) -> None:
        """Notify listeners for the changed object or a polling refresh."""
        data = self.data
        changed_obj_id = data[1] if data is not None else None
        for update_callback, context in list(self._listeners.values()):
            if changed_obj_id is not None and isinstance(context, tuple):
                if changed_obj_id not in context:
                    continue
            try:
                update_callback()
            except Exception:
                self.logger.exception(
                    "Unexpected error updating listener %s for %s",
                    id(update_callback),
                    self.name,
                )
