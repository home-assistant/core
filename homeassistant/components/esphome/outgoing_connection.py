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


@singleton(_KEY_OUTGOING_CONNECTION_LISTENER, async_=True)
async def _async_get_listener(hass: HomeAssistant) -> _ListenerState:
    """Start the shared listener; raises OSError when the port cannot be bound.

    Raising keeps the singleton uncached so the next registration retries.
    """
    if (stopping := hass.data.pop(_KEY_OUTGOING_CONNECTION_STOPPING, None)) is not None:
        # Wait for the previous listener to release the port before rebinding
        await stopping
    server = OutgoingConnectionServer()
    await server.start()

    async def _async_stop(event: Event) -> None:
        # Drop the cached instance so late registrations cannot attach to it
        hass.data.pop(_KEY_OUTGOING_CONNECTION_LISTENER, None)
        await server.stop()

    remove_stop_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, _async_stop
    )
    return _ListenerState(server, remove_stop_listener)


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
            _LOGGER.warning(
                (
                    "Cannot listen for ESPHome outgoing connections on port %s: %s;"
                    " devices are still told to dial back and will retry"
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

    @callback
    def _async_unregister() -> None:
        unregister()
        state.registrations -= 1
        # Already popped when Home Assistant is stopping
        if (
            state.registrations == 0
            and hass.data.get(_KEY_OUTGOING_CONNECTION_LISTENER) is state
        ):
            del hass.data[_KEY_OUTGOING_CONNECTION_LISTENER]
            state.remove_stop_listener()
            # Tracked so the next registration waits for the port release
            hass.data[_KEY_OUTGOING_CONNECTION_STOPPING] = hass.async_create_task(
                state.server.stop()
            )

    return _async_unregister
