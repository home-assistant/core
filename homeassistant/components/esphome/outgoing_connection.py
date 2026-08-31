"""Shared listener for ESPHome device-initiated connections."""

import logging

from aioesphomeapi import OutgoingConnectionServer, ReconnectLogic

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.singleton import singleton
from homeassistant.util.hass_dict import HassKey

from .const import CONF_ALLOW_OUTGOING_CONNECTION, DEFAULT_ALLOW_OUTGOING_CONNECTION
from .entry_data import ESPHomeConfigEntry

_LOGGER = logging.getLogger(__name__)

KEY_OUTGOING_CONNECTION_SERVER: HassKey[OutgoingConnectionServer | None] = HassKey(
    "esphome_outgoing_connection_server"
)


@callback
def outgoing_connection_enabled(entry: ESPHomeConfigEntry) -> bool:
    """Return True when the entry opts into device-initiated connections."""
    return bool(
        entry.options.get(
            CONF_ALLOW_OUTGOING_CONNECTION, DEFAULT_ALLOW_OUTGOING_CONNECTION
        )
    )


@singleton(KEY_OUTGOING_CONNECTION_SERVER, async_=True)
async def _async_get_server(hass: HomeAssistant) -> OutgoingConnectionServer | None:
    """Get the process-wide listener; None when the port cannot be bound."""
    server = OutgoingConnectionServer()
    try:
        await server.start()
    except OSError as err:
        _LOGGER.warning("Cannot listen for ESPHome outgoing connections: %s", err)
        return None

    async def _async_stop(event: Event) -> None:
        await server.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    return server


async def async_register_outgoing_target(
    hass: HomeAssistant, mac: str, reconnect_logic: ReconnectLogic
) -> CALLBACK_TYPE | None:
    """Route dial-ins from this MAC to the reconnect logic.

    Returns the unregister callback, or None when the listener could not be
    started (the failure is logged once for the whole process).
    """
    if (server := await _async_get_server(hass)) is None:
        return None
    return server.register(mac, reconnect_logic)
