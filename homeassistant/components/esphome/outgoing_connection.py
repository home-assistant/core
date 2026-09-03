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


@callback
def _async_stop_listener(hass: HomeAssistant, state: _ListenerState) -> None:
    # Drops the cached listener and stops it; the caller checked ownership
    del hass.data[_KEY_OUTGOING_CONNECTION_LISTENER]
    state.remove_stop_listener()
    # Tracked so the next registration waits for the port release
    stopping = hass.async_create_task(state.server.stop())
    stopping.add_done_callback(_log_stop_failure)
    hass.data[_KEY_OUTGOING_CONNECTION_STOPPING] = stopping


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
            # Still stopping; keep it so the next attempt can wait on it. The
            # bind below then likely fails, so name the real cause loudly
            _LOGGER.warning("Previous outgoing connection listener is still stopping")
            hass.data[_KEY_OUTGOING_CONNECTION_STOPPING] = stopping
    server = OutgoingConnectionServer()
    await server.start()
    if hass.data.pop(_KEY_OUTGOING_CONNECTION_BIND_FAILED, None) is not None:
        _LOGGER.info(
            "Listening for ESPHome outgoing connections on port %s",
            DEFAULT_OUTGOING_CONNECTION_PORT,
        )

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
        failed = False
        try:
            unregister()
        except Exception:
            # A cleanup callback must not abort the entry's remaining cleanup
            failed = True
            _LOGGER.exception("Error removing the dial-in route")
        finally:
            state.registrations -= 1
            # In the finally so a raising unregister cannot leave a routeless
            # listener holding the port; a failed removal tears the whole
            # listener down so the routes and the count cannot diverge.
            # Already popped when HA is stopping.
            if (state.registrations == 0 or failed) and hass.data.get(
                _KEY_OUTGOING_CONNECTION_LISTENER
            ) is state:
                _async_stop_listener(hass, state)


async def async_register_outgoing_target(
    hass: HomeAssistant, mac: str, reconnect_logic: ReconnectLogic
) -> CALLBACK_TYPE | None:
    """Route dial-ins from this MAC to the reconnect logic.

    Returns the unregister callback, or None when the listening port cannot
    be bound. The last unregistration stops the listener and frees the port.
    """
    while True:
        try:
            state = await _async_get_listener(hass)
        except OSError as err:
            # One warning per failure window, not one per registered device;
            # INFO after that so a deliberate retry still reports its outcome
            now = hass.loop.time()
            last = hass.data.get(
                _KEY_OUTGOING_CONNECTION_BIND_FAILED, -_BIND_WARN_INTERVAL
            )
            level = logging.INFO
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
        if hass.is_stopping:
            # The STOP event may have fired while binding, in which case the
            # one-shot listener missed it and nothing else would stop this
            # instance; a shared listener others route through is left alone
            if (
                state.registrations == 0
                and hass.data.get(_KEY_OUTGOING_CONNECTION_LISTENER) is state
            ):
                _async_stop_listener(hass, state)
            return None
        if hass.data.get(_KEY_OUTGOING_CONNECTION_LISTENER) is state:
            break
        # Popped and stopped while we awaited it; build a fresh listener
    unregister = state.server.register(mac, reconnect_logic)
    state.registrations += 1
    return _Registration(hass, state, unregister).async_unregister
