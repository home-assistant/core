"""Shared listener for ESPHome device-initiated connections."""

import asyncio
from dataclasses import dataclass
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

# Bound on waiting for a previous listener to stop before rebinding
_STOP_TIMEOUT = 10.0
# A recurring bind failure re-warns after this long instead of staying debug
_BIND_WARN_INTERVAL = 3600.0


@dataclass
class _ListenerState:
    """The shared listener with its registration count and stop listener."""

    server: OutgoingConnectionServer
    remove_stop_listener: CALLBACK_TYPE
    registrations: int = 0


_KEY_OUTGOING_CONNECTION_LISTENER: HassKey[_ListenerState] = HassKey(
    "esphome_outgoing_connection_listener"
)
_KEY_OUTGOING_CONNECTION_STOPPING: HassKey[asyncio.Task[None]] = HassKey(
    "esphome_outgoing_connection_stopping"
)
# Monotonic time of the last bind-failure warning
_KEY_OUTGOING_CONNECTION_BIND_FAILED: HassKey[float] = HassKey(
    "esphome_outgoing_connection_bind_failed"
)


def _log_stop_failure(task: asyncio.Task[None]) -> None:
    if not task.cancelled() and (exc := task.exception()) is not None:
        _LOGGER.warning(
            "Failed to stop the outgoing connection listener; port %s may stay bound",
            DEFAULT_OUTGOING_CONNECTION_PORT,
            exc_info=exc,
        )


@singleton(_KEY_OUTGOING_CONNECTION_LISTENER, async_=True)
async def _async_get_listener(hass: HomeAssistant) -> _ListenerState:
    """Start the shared listener; raises OSError when the port cannot be bound.

    Raising keeps the singleton uncached so the next registration retries.
    """
    if (stopping := hass.data.pop(_KEY_OUTGOING_CONNECTION_STOPPING, None)) is not None:
        # Wait for the previous listener to release the port before rebinding;
        # wait() absorbs its failure or cancellation (logged by its done
        # callback), and a still-bound port surfaces as OSError from start()
        done, _ = await asyncio.wait([stopping], timeout=_STOP_TIMEOUT)
        if not done:
            # Still stopping; keep it so the next attempt can wait on it
            hass.data[_KEY_OUTGOING_CONNECTION_STOPPING] = stopping
    server = OutgoingConnectionServer()
    await server.start()
    hass.data.pop(_KEY_OUTGOING_CONNECTION_BIND_FAILED, None)

    async def _async_stop(event: Event) -> None:
        # Drop the cached instance so late registrations cannot attach to it
        hass.data.pop(_KEY_OUTGOING_CONNECTION_LISTENER, None)
        await server.stop()

    remove_stop_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, _async_stop
    )
    return _ListenerState(server, remove_stop_listener)


class _Registration:
    """One MAC registration; unregisters exactly once."""

    __slots__ = ("_hass", "_state", "_unregister")

    def __init__(
        self, hass: HomeAssistant, state: _ListenerState, unregister: CALLBACK_TYPE
    ) -> None:
        self._hass = hass
        self._state = state
        self._unregister: CALLBACK_TYPE | None = unregister

    @callback
    def async_unregister(self) -> None:
        """Remove the route; the last one stops the listener."""
        if (unregister := self._unregister) is None:
            return
        self._unregister = None
        hass = self._hass
        state = self._state
        try:
            unregister()
        finally:
            state.registrations -= 1
        # Already popped when Home Assistant is stopping
        if (
            state.registrations == 0
            and hass.data.get(_KEY_OUTGOING_CONNECTION_LISTENER) is state
        ):
            del hass.data[_KEY_OUTGOING_CONNECTION_LISTENER]
            state.remove_stop_listener()
            # Tracked so the next registration waits for the port release
            stopping = hass.async_create_task(state.server.stop())
            stopping.add_done_callback(_log_stop_failure)
            hass.data[_KEY_OUTGOING_CONNECTION_STOPPING] = stopping


async def async_register_outgoing_target(
    hass: HomeAssistant, mac: str, reconnect_logic: ReconnectLogic
) -> CALLBACK_TYPE | None:
    """Route dial-ins from this MAC to the reconnect logic.

    Returns the unregister callback, or None when the listening port cannot
    be bound. The last unregistration stops the listener and frees the port.
    """
    while not hass.is_stopping:
        try:
            state = await _async_get_listener(hass)
        except OSError as err:
            # One warning per failure window, not one per registered device
            now = hass.loop.time()
            last = hass.data.get(
                _KEY_OUTGOING_CONNECTION_BIND_FAILED, -_BIND_WARN_INTERVAL
            )
            level = logging.DEBUG
            if now - last >= _BIND_WARN_INTERVAL:
                hass.data[_KEY_OUTGOING_CONNECTION_BIND_FAILED] = now
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
            return None
        if hass.data.get(_KEY_OUTGOING_CONNECTION_LISTENER) is state:
            break
        # Popped and stopped while we awaited it; build a fresh listener
    else:
        return None
    unregister = state.server.register(mac, reconnect_logic)
    state.registrations += 1
    return _Registration(hass, state, unregister).async_unregister
