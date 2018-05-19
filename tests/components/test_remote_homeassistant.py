"""The tests for the remote_homeassistant platform."""
import asyncio
from unittest.mock import patch

from homeassistant.setup import async_setup_component
from homeassistant.components import remote_homeassistant as rass

from tests.common import async_test_home_assistant


async def test_something(hass, aiohttp_client):
    """Test bla."""
    assert await async_setup_component(hass, 'websocket_api', {})
    client = await aiohttp_client(hass.http.app)

    hass_client = await async_test_home_assistant(hass.loop)

    with patch('homeassistant.components.remote_homeassistant'
               '.async_get_clientsession', return_value=client), \
            patch('homeassistant.components.remote_homeassistant'
                  '.RemoteConnection._get_url', return_value='/api/websocket'):
        assert await async_setup_component(hass_client, rass.DOMAIN, {
            rass.DOMAIN: {
                'instances': {
                    'host': 'mock',
                }
            }
        })

    hass.states.async_set('light.kitchen', 'on')
    # await hass.async_block_till_done()
    # await hass_client.async_block_till_done()
    await asyncio.sleep(.1)

    state = hass_client.states.get('light.kitchen')
    assert state is not None
    assert state.state == 'on'
