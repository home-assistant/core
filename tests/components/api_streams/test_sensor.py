"""Test cases for the API stream sensor."""
import asyncio
import logging
import pytest

from homeassistant.bootstrap import async_setup_component
from tests.common import assert_setup_component


@pytest.mark.skip(reason="test fails randomly due to race condition.")
async def test_api_streams(hass):
    """Test API streams."""
    log = logging.getLogger('homeassistant.components.api')

    with assert_setup_component(1):
        await async_setup_component(hass, 'sensor', {
            'sensor': {
                'platform': 'api_streams',
            }
        })

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '0'

    log.debug('STREAM 1 ATTACHED')
    await asyncio.sleep(0.1)

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '1'

    log.debug('STREAM 1 ATTACHED')
    await asyncio.sleep(0.1)

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '2'

    log.debug('STREAM 1 RESPONSE CLOSED')
    await asyncio.sleep(0.1)

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '1'


@pytest.mark.skip(reason="test fails randomly due to race condition.")
async def test_websocket_api(hass):
    """Test API streams."""
    log = logging.getLogger('homeassistant.components.websocket_api')

    with assert_setup_component(1):
        await async_setup_component(hass, 'sensor', {
            'sensor': {
                'platform': 'api_streams',
            }
        })

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '0'

    log.debug('WS %s: %s', id(log), 'Connected')
    await asyncio.sleep(0.1)

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '1'

    log.debug('WS %s: %s', id(log), 'Connected')
    await asyncio.sleep(0.1)

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '2'

    log.debug('WS %s: %s', id(log), 'Closed connection')
    await asyncio.sleep(0.1)

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '1'
