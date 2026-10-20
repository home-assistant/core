"""UniFi Network data update coordinator."""

from datetime import timedelta
from typing import TYPE_CHECKING, override

import aiounifi
from aiounifi import EndpointNotFound
from aiounifi.interfaces.api_handlers import APIHandler, ItemEvent

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

if TYPE_CHECKING:
    from .hub.hub import UnifiHub

POLL_INTERVAL = timedelta(seconds=10)
IDLE_POLL_INTERVAL = timedelta(minutes=10)


class UnifiDataUpdateCoordinator[HandlerT: APIHandler](
    DataUpdateCoordinator[tuple[ItemEvent, str] | None]
):
    """Coordinator managing websocket or polling updates for a UniFi API handler."""

    def __init__(
        self,
        hub: UnifiHub,
        handler: HandlerT,
        *,
        disable_polling_on_endpoint_not_found: bool = False,
    ) -> None:
        """Initialize coordinator."""
        supports_websocket = bool(handler.process_messages or handler.remove_messages)
        self._supports_websocket = supports_websocket
        super().__init__(
            hub.hass,
            LOGGER,
            name=f"UniFi {type(handler).__name__}",
            config_entry=hub.config.entry,
            update_interval=None if supports_websocket else POLL_INTERVAL,
        )
        self._handler = handler
        self._connection = hub.connection
        self._disable_polling_on_endpoint_not_found = (
            disable_polling_on_endpoint_not_found
        )
        self._endpoint_not_found_logged = False

        hub.config.entry.async_on_unload(handler.subscribe(self._async_handle_update))
        hub.config.entry.async_on_unload(
            async_dispatcher_connect(
                hub.hass, hub.signal_reachable, self._async_reachable_changed
            )
        )

    @property
    def handler(self) -> HandlerT:
        """Return the aiounifi handler managed by this coordinator."""
        return self._handler

    @override
    async def _async_update_data(self) -> None:
        """Update data from the API handler."""
        if not self._connection.available:
            raise UpdateFailed("UniFi Network connection is unavailable")

        try:
            await self._handler.update()
        except EndpointNotFound as err:
            if (
                self._disable_polling_on_endpoint_not_found
                and not self._endpoint_not_found_logged
            ):
                self._endpoint_not_found_logged = True
                self.update_interval = None
                self.logger.warning(
                    "UniFi %s endpoint is unavailable; disabling polling",
                    type(self._handler).__name__,
                )
            raise UpdateFailed(str(err)) from err
        except (TimeoutError, aiounifi.RequestError) as err:
            self._connection.verify_session(err)
            raise UpdateFailed(str(err)) from err
        except aiounifi.AiounifiException as err:
            raise UpdateFailed(str(err)) from err

        if self.update_interval is not None:
            self.update_interval = (
                POLL_INTERVAL if self._handler.items() else IDLE_POLL_INTERVAL
            )

    @callback
    def _async_reachable_changed(self) -> None:
        """Pause polling while the session is down, recovery refetches."""
        if not self._connection.available:
            self._unschedule_refresh()

    @callback
    @override
    def _schedule_refresh(self) -> None:
        """Only poll while the session is up, a refresh in flight must not resume it."""
        if self._connection.available:
            super()._schedule_refresh()

    async def async_resync(self) -> None:
        """Refetch handler data after the connection is restored."""
        if not self._supports_websocket:
            await self.async_refresh()
            return

        # Pushed data stays valid if the refetch fails, the websocket resumes after it
        try:
            await self._handler.update()
        except (TimeoutError, aiounifi.RequestError) as err:
            self._connection.verify_session(err)
        except aiounifi.AiounifiException as err:
            LOGGER.debug(
                "Could not refetch UniFi %s data: %s", type(self._handler).__name__, err
            )

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
