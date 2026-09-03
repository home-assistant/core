"""Shared listener for ESPHome device-initiated connections."""

import logging

from aioesphomeapi import (
    DEFAULT_OUTGOING_CONNECTION_PORT,
    OutgoingConnectionServer,
    ReconnectLogic,
)

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.singleton import singleton
from homeassistant.util.hass_dict import HassKey

_LOGGER = logging.getLogger(__name__)

# A recurring bind failure re-warns after this long instead of staying at info
_BIND_WARN_INTERVAL = 3600.0

_KEY_OUTGOING_CONNECTION_MANAGER: HassKey[_OutgoingConnectionManager] = HassKey(
    "esphome_outgoing_connection_manager"
)


class _Registration:
    """One MAC registration; unregisters exactly once."""

    __slots__ = ("_mac", "_manager", "_server", "_unregister")

    def __init__(
        self,
        manager: _OutgoingConnectionManager,
        server: OutgoingConnectionServer,
        mac: str,
        unregister: CALLBACK_TYPE,
    ) -> None:
        self._manager = manager
        self._server = server
        self._mac = mac
        self._unregister: CALLBACK_TYPE | None = unregister

    @callback
    def async_unregister(self) -> None:
        """Remove the route; the last one stops the listener."""
        if (unregister := self._unregister) is None:
            return
        self._unregister = None
        self._manager.async_remove_registration(self._server, self._mac, unregister)


class _OutgoingConnectionManager:
    """Owns the shared dial-in listener for this Home Assistant instance.

    Fully synchronous: the library binds without awaiting and guarantees the
    port is free when close() returns, so there are no suspension points
    here, no races to manage, and a replacement listener can always bind.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._server: OutgoingConnectionServer | None = None
        self._registrations = 0
        self._remove_stop_listener: CALLBACK_TYPE | None = None
        # None until a bind fails; holds the last warning time after
        self._last_bind_warning: float | None = None

    @callback
    def async_register(
        self, mac: str, reconnect_logic: ReconnectLogic
    ) -> CALLBACK_TYPE | None:
        """Route dial-ins from this MAC; returns the unregister callback.

        None when the listening port cannot be bound. The last
        unregistration stops the listener and frees the port.
        """
        hass = self._hass
        if (server := self._server) is None:
            if hass.is_stopping:
                return None
            server = OutgoingConnectionServer()
            try:
                server.start()
            except OSError as err:
                self._async_log_bind_failure(err)
                return None
            if self._last_bind_warning is not None:
                self._last_bind_warning = None
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
                self._async_close_server()
            raise
        self._registrations += 1
        return _Registration(self, server, mac, unregister).async_unregister

    @callback
    def async_remove_registration(
        self, server: OutgoingConnectionServer, mac: str, unregister: CALLBACK_TYPE
    ) -> None:
        """Remove one route; called at most once per registration."""
        if server is not self._server:
            return  # that listener is already gone, along with its routes
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
                self._async_close_server()

    @callback
    def _async_close_server(self) -> None:
        server = self._server
        self._server = None
        self._registrations = 0
        if (remove := self._remove_stop_listener) is not None:
            self._remove_stop_listener = None
            remove()
        if server is not None:
            server.close()

    @callback
    def _async_hass_stop(self, event: Event) -> None:
        self._async_close_server()

    @callback
    def _async_log_bind_failure(self, err: OSError) -> None:
        # One warning per failure window, not one per registered device;
        # info after that so a deliberate retry still reports its outcome
        now = self._hass.loop.time()
        last = self._last_bind_warning
        level = logging.INFO
        if last is None or now - last >= _BIND_WARN_INTERVAL:
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


@singleton(_KEY_OUTGOING_CONNECTION_MANAGER)
@callback
def _async_get_manager(hass: HomeAssistant) -> _OutgoingConnectionManager:
    return _OutgoingConnectionManager(hass)


@callback
def async_register_outgoing_target(
    hass: HomeAssistant, mac: str, reconnect_logic: ReconnectLogic
) -> CALLBACK_TYPE | None:
    """Route dial-ins from this MAC to the reconnect logic.

    Returns the unregister callback, or None when the listening port cannot
    be bound. The last unregistration stops the listener and frees the port.
    """
    return _async_get_manager(hass).async_register(mac, reconnect_logic)
