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

_KEY_OUTGOING_CONNECTION_SERVER: HassKey[OutgoingConnectionServer] = HassKey(
    "esphome_outgoing_connection_server"
)
_KEY_OUTGOING_CONNECTION_COUNT: HassKey[int] = HassKey(
    "esphome_outgoing_connection_count"
)


@singleton(_KEY_OUTGOING_CONNECTION_SERVER, async_=True)
async def _async_get_server(hass: HomeAssistant) -> OutgoingConnectionServer:
    """Start the shared listener; raises OSError when the port cannot be bound.

    Raising keeps the singleton uncached so the next registration retries.
    """
    server = OutgoingConnectionServer()
    await server.start()

    async def _async_stop(event: Event) -> None:
        # Drop the cached instance so late registrations cannot attach to it
        hass.data.pop(_KEY_OUTGOING_CONNECTION_SERVER, None)
        await server.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    return server


async def async_register_outgoing_target(
    hass: HomeAssistant, mac: str, reconnect_logic: ReconnectLogic
) -> CALLBACK_TYPE | None:
    """Route dial-ins from this MAC to the reconnect logic.

    Returns the unregister callback, or None when the listening port cannot
    be bound. The last unregistration stops the listener and frees the port.
    """
    while not hass.is_stopping:
        try:
            server = await _async_get_server(hass)
        except OSError as err:
            _LOGGER.warning(
                "Cannot listen for ESPHome outgoing connections on port %s: %s",
                DEFAULT_OUTGOING_CONNECTION_PORT,
                err,
            )
            return None
        if hass.data.get(_KEY_OUTGOING_CONNECTION_SERVER) is server:
            break
        # Popped and stopped while we awaited it; build a fresh listener
    else:
        return None
    unregister = server.register(mac, reconnect_logic)
    hass.data[_KEY_OUTGOING_CONNECTION_COUNT] = (
        hass.data.get(_KEY_OUTGOING_CONNECTION_COUNT, 0) + 1
    )

    @callback
    def _async_unregister() -> None:
        unregister()
        hass.data[_KEY_OUTGOING_CONNECTION_COUNT] -= 1
        if (
            hass.data[_KEY_OUTGOING_CONNECTION_COUNT] == 0
            # Already popped when Home Assistant is stopping
            and hass.data.pop(_KEY_OUTGOING_CONNECTION_SERVER, None) is not None
        ):
            hass.async_create_task(server.stop())

    return _async_unregister
