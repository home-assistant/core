"""Shared listener for ESPHome device-initiated connections."""

import asyncio
import logging

from aioesphomeapi import (
    DEFAULT_OUTGOING_CONNECTION_PORT,
    OutgoingConnectionServer,
    ReconnectLogic,
)

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.util.hass_dict import HassKey

_LOGGER = logging.getLogger(__name__)

# A recurring bind failure re-warns after this long instead of staying at info
_BIND_WARN_INTERVAL = 3600.0

_KEY_OUTGOING_CONNECTION_MANAGER: HassKey[_OutgoingConnectionManager] = HassKey(
    "esphome_outgoing_connection_manager"
)


def _log_stop_failure(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        _LOGGER.debug("Outgoing connection listener stop was cancelled")
        return
    if (exc := task.exception()) is not None:
        _LOGGER.warning(
            "Failed to stop the outgoing connection listener; port %s may stay bound",
            DEFAULT_OUTGOING_CONNECTION_PORT,
            exc_info=exc,
        )


class _Registration:
    """One MAC registration; unregisters exactly once."""

    __slots__ = ("_mac", "_manager", "_unregister")

    def __init__(
        self,
        manager: _OutgoingConnectionManager,
        mac: str,
        unregister: CALLBACK_TYPE,
    ) -> None:
        self._manager = manager
        self._mac = mac
        self._unregister: CALLBACK_TYPE | None = unregister

    @callback
    def async_unregister(self) -> None:
        """Remove the route; the last one stops the listener."""
        if (unregister := self._unregister) is None:
            return
        self._unregister = None
        self._manager.async_remove_registration(self._mac, unregister)


class _OutgoingConnectionManager:
    """Owns the shared dial-in listener for this Home Assistant instance.

    The library releases the port before its stop() first awaits, so a
    replacement listener can always bind immediately and stops need no
    cross-listener serialization here.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._server: OutgoingConnectionServer | None = None
        self._registrations = 0
        self._lock = asyncio.Lock()
        self._remove_stop_listener: CALLBACK_TYPE | None = None
        self._last_bind_warning = -_BIND_WARN_INTERVAL
        self._bind_failed = False

    async def async_register(
        self, mac: str, reconnect_logic: ReconnectLogic
    ) -> CALLBACK_TYPE | None:
        """Route dial-ins from this MAC; returns the unregister callback.

        None when the listening port cannot be bound. The last
        unregistration stops the listener and frees the port.
        """
        async with self._lock:
            hass = self._hass
            if (server := self._server) is None:
                server = OutgoingConnectionServer()
                try:
                    await server.start()
                except OSError as err:
                    self._async_log_bind_failure(err)
                    return None
                if hass.is_stopping:
                    # Shutting down (possibly since before the bind); the
                    # one-shot listener below would never hear the STOP event
                    self._async_schedule_stop(server)
                    return None
                if self._bind_failed:
                    self._bind_failed = False
                    self._last_bind_warning = -_BIND_WARN_INTERVAL
                    _LOGGER.info(
                        "Listening for ESPHome outgoing connections on port %s",
                        DEFAULT_OUTGOING_CONNECTION_PORT,
                    )
                self._server = server
                self._remove_stop_listener = hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STOP, self._async_hass_stop
                )
            try:
                unregister = server.register(mac, reconnect_logic)
            except BaseException:
                # A freshly started listener with no registrations would
                # otherwise hold the port for the rest of the run
                if self._registrations == 0:
                    self._async_stop_server()
                raise
            self._registrations += 1
        return _Registration(self, mac, unregister).async_unregister

    @callback
    def async_remove_registration(self, mac: str, unregister: CALLBACK_TYPE) -> None:
        """Remove one route; called at most once per registration."""
        failed = False
        try:
            unregister()
        except Exception:
            # A cleanup callback must not abort the entry's remaining cleanup
            _LOGGER.exception("Error removing the dial-in route")
            try:
                if self._server is not None:
                    # The targeted recovery keeps the other entries routed
                    self._server.discard(mac)
            except Exception:
                failed = True
                _LOGGER.exception("Error discarding the dial-in route")
                if self._registrations > 1:
                    _LOGGER.warning(
                        (
                            "Stopping the outgoing connection listener; %s other"
                            " device(s) will not receive dial-ins until their"
                            " entries are reloaded"
                        ),
                        self._registrations - 1,
                    )
        finally:
            self._registrations -= 1
            # When even discard failed the routes are unknowable, so the
            # whole listener is torn down
            if self._server is not None and (self._registrations == 0 or failed):
                self._async_stop_server()

    @callback
    def _async_stop_server(self) -> None:
        server = self._server
        self._server = None
        if (remove := self._remove_stop_listener) is not None:
            self._remove_stop_listener = None
            remove()
        if server is not None:
            self._async_schedule_stop(server)

    @callback
    def _async_schedule_stop(self, server: OutgoingConnectionServer) -> None:
        # Fire and forget: the library frees the port before stop() first
        # awaits, so nothing needs to wait; the callback logs a failure
        self._hass.async_create_task(server.stop()).add_done_callback(_log_stop_failure)

    async def _async_hass_stop(self, event: Event) -> None:
        if (server := self._server) is None:
            return
        self._server = None
        self._remove_stop_listener = None
        await server.stop()

    @callback
    def _async_log_bind_failure(self, err: OSError) -> None:
        # One warning per failure window, not one per registered device;
        # info after that so a deliberate retry still reports its outcome
        self._bind_failed = True
        now = self._hass.loop.time()
        level = logging.INFO
        if now - self._last_bind_warning >= _BIND_WARN_INTERVAL:
            self._last_bind_warning = now
            level = logging.WARNING
        _LOGGER.log(
            level,
            (
                "Cannot listen for ESPHome outgoing connections on port %s: %s;"
                " devices are still told to dial back, reload an ESPHome entry"
                " to retry the bind"
            ),
            DEFAULT_OUTGOING_CONNECTION_PORT,
            err,
        )


async def async_register_outgoing_target(
    hass: HomeAssistant, mac: str, reconnect_logic: ReconnectLogic
) -> CALLBACK_TYPE | None:
    """Route dial-ins from this MAC to the reconnect logic.

    Returns the unregister callback, or None when the listening port cannot
    be bound. The last unregistration stops the listener and frees the port.
    """
    if (manager := hass.data.get(_KEY_OUTGOING_CONNECTION_MANAGER)) is None:
        manager = hass.data[_KEY_OUTGOING_CONNECTION_MANAGER] = (
            _OutgoingConnectionManager(hass)
        )
    return await manager.async_register(mac, reconnect_logic)
