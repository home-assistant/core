"""Test cases for the API stream sensor."""
import pytest
from homeassistant.bootstrap import async_setup_component
from tests.common import assert_setup_component
from homeassistant.components.websocket_api.auth import TYPE_AUTH_REQUIRED
from tests.components.websocket_api.test_auth import test_auth_via_msg
from homeassistant.components.websocket_api.http import URL
from tests.components.websocket_api import API_PASSWORD


@pytest.fixture
def no_auth_websocket_client(hass, loop, aiohttp_client):
    """Websocket connection that requires authentication."""
    assert loop.run_until_complete(
        async_setup_component(hass, 'websocket_api', {
            'http': {
                'api_password': API_PASSWORD
            }
        }))

    client = loop.run_until_complete(aiohttp_client(hass.http.app))
    ws = loop.run_until_complete(client.ws_connect(URL))

    auth_ok = loop.run_until_complete(ws.receive_json())
    assert auth_ok['type'] == TYPE_AUTH_REQUIRED

    yield ws

    if not ws.closed:
        loop.run_until_complete(ws.close())


async def test_api_streams(hass, no_auth_websocket_client, legacy_auth):
    """Test API streams."""
    with assert_setup_component(1):
        await async_setup_component(hass, 'sensor', {
            'sensor': {
                'platform': 'api_streams',
            }
        })

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '0'

    await test_auth_via_msg(no_auth_websocket_client, legacy_auth)

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '1'

    await no_auth_websocket_client.close()
    await hass.async_block_till_done()

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '0'
