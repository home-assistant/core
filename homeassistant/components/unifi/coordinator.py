"""UniFi Network data update coordinator."""

import asyncio
from datetime import timedelta
import json
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
# Large sites can take a while to list all clients
UPDATE_TIMEOUT = 30

# Errors after which the session is checked. A half started application can
# answer with invalid JSON, and aiounifi raises LoginRequired once it does not
# log in again on its own, or the answer of its own login. Unlike
# NOT_READY_ERRORS of the readiness probe, a rejection of a single request
# does not check the session.
SESSION_CHECK_ERRORS = (
    TimeoutError,
    json.JSONDecodeError,
    aiounifi.AuthenticationRateLimitError,
    aiounifi.LoginRequired,
    aiounifi.RequestError,
    aiounifi.TwoFaTokenRequired,
)


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
        super().__init__(
            hub.hass,
            LOGGER,
            name=f"UniFi {type(handler).__name__}",
            config_entry=hub.config.entry,
            update_interval=None if supports_websocket else POLL_INTERVAL,
        )
        self._handler = handler
        self._supports_websocket = supports_websocket
        self._connection = hub.connection
        self._disable_polling_on_endpoint_not_found = (
            disable_polling_on_endpoint_not_found
        )
        self._endpoint_not_found_logged = False
        self._resync_task: asyncio.Task[None] | None = None

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
        try:
            async with asyncio.timeout(UPDATE_TIMEOUT):
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
        except SESSION_CHECK_ERRORS as err:
            self._connection.verify_session(err)
            raise UpdateFailed(str(err) or type(err).__name__) from err
        except aiounifi.AiounifiException as err:
            if not self._supports_websocket:
                raise UpdateFailed(str(err)) from err
            self.logger.warning("Error fetching %s data: %s", self.name, err)

        if self.update_interval is not None:
            self.update_interval = (
                POLL_INTERVAL if self._handler.items() else IDLE_POLL_INTERVAL
            )

    @callback
    def _async_reachable_changed(self) -> None:
        """Pause polling while the session is down, recovery refetches."""
        if not self._connection.available:
            self._unschedule_refresh()
            if self._resync_task is not None:
                # It can still wait for an older poll to free the refresh lock
                self._resync_task.cancel()
                self._resync_task = None

    @callback
    @override
    def _schedule_refresh(self) -> None:
        """Only poll while the session is up, a refresh in flight must not resume it."""
        if self._connection.available:
            super()._schedule_refresh()

    async def async_resync(self) -> None:
        """Refetch handler data after the connection is restored."""
        if not self._supports_websocket:
            # A poll from before the outage can hold the refresh lock, don't
            # let it hold up the recovery
            self._resync_task = (
                self._connection.config_entry.async_create_background_task(
                    self.hass, self.async_refresh(), f"unifi_resync_{self.name}"
                )
            )
            return

        # Pushed data stays valid if the refetch fails, the websocket resumes after it
        name = type(self._handler).__name__
        try:
            async with asyncio.timeout(UPDATE_TIMEOUT):
                await self._handler.update()
        except SESSION_CHECK_ERRORS as err:
            self._connection.verify_session(err)
        except aiounifi.AiounifiException as err:
            LOGGER.debug("Could not refetch UniFi %s data: %s", name, err)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error refetching UniFi %s data", name)

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
