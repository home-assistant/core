"""Test cases for the API stream sensor."""

from homeassistant.bootstrap import async_setup_component

from tests.common import assert_setup_component
from .test_auth import test_auth_via_msg


async def test_websocket_api(hass, no_auth_websocket_client, legacy_auth):
    """Test API streams."""
    with assert_setup_component(1):
        await async_setup_component(hass, 'sensor', {
            'sensor': {
                'platform': 'websocket_api',
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
