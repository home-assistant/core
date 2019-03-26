"""Test connection of websocket API."""

from homeassistant.components.websocket.connection import ActiveConnection

def test_auth_via_msg(no_auth_websocket_client, legacy_auth):