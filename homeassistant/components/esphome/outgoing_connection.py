"""Shared listener for ESPHome device-initiated connections."""

from aioesphomeapi import OutgoingConnectionServer, ReconnectLogic

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.singleton import singleton
from homeassistant.util.hass_dict import HassKey

_KEY_OUTGOING_CONNECTION_SERVER: HassKey[OutgoingConnectionServer] = HassKey(
    "esphome_outgoing_connection_server"
)


@singleton(_KEY_OUTGOING_CONNECTION_SERVER)
@callback
def _async_get_server(hass: HomeAssistant) -> OutgoingConnectionServer:
    """Create the shared listener and tie it to Home Assistant's shutdown."""
    server = OutgoingConnectionServer()

    @callback
    def _async_hass_stop(event: Event) -> None:
        # Evict the singleton too: a registration after stop must build a
        # fresh server, not hand a route to this closed one
        hass.data.pop(_KEY_OUTGOING_CONNECTION_SERVER, None)
        server.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_hass_stop)
    return server


@callback
def async_register_outgoing_target(
    hass: HomeAssistant, mac: str, reconnect_logic: ReconnectLogic
) -> CALLBACK_TYPE | None:
    """Route dial-ins from this MAC to the reconnect logic.

    The library manages the listener lifecycle. Returns the unregister
    callback, or None during shutdown.
    """
    if hass.is_stopping:
        return None
    return _async_get_server(hass).register(mac, reconnect_logic)
