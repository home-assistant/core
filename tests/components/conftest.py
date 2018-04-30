import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components import websocket_api as wapi


@pytest.fixture
def websocket_client(loop, hass, aiohttp_client):
    """Websocket client fixture connected to websocket server."""
    assert loop.run_until_complete(
        async_setup_component(hass, 'websocket_api'))

    client = loop.run_until_complete(aiohttp_client(hass.http.app))
    ws = loop.run_until_complete(client.ws_connect(wapi.URL))
    auth_ok = loop.run_until_complete(ws.receive_json())
    assert auth_ok['type'] == wapi.TYPE_AUTH_OK

    yield ws

    if not ws.closed:
        loop.run_until_complete(ws.close())
