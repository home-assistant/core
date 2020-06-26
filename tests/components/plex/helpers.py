"""Helper methods for Plex tests."""
from homeassistant.components.plex.const import DOMAIN, WEBSOCKETS


def trigger_plex_update(hass, plex_server):
    """Call the websocket callback method."""
    server_id = plex_server.machineIdentifier
    websocket = hass.data[DOMAIN][WEBSOCKETS][server_id]
    websocket.callback()
