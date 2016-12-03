import asyncio
import logging

from homeassistant.bootstrap import async_setup_component
from tests.common import assert_setup_component


@asyncio.coroutine
def test_api_streams(hass):
    """Test API streams."""
    log = logging.getLogger('homeassistant.components.api')

    with assert_setup_component(1):
        yield from async_setup_component(hass, 'sensor', {
            'sensor': {
                'platform': 'api_streams',
            }
        })

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '0'

    log.debug('STREAM 1 ATTACHED')
    yield from hass.async_block_till_done()

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '1'

    log.debug('STREAM 1 ATTACHED')
    yield from hass.async_block_till_done()

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '2'

    log.debug('STREAM 1 RESPONSE CLOSED')
    yield from hass.async_block_till_done()

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '1'


@asyncio.coroutine
def test_websocket_api(hass):
    """Test API streams."""
    log = logging.getLogger('homeassistant.components.websocket_api')

    with assert_setup_component(1):
        yield from async_setup_component(hass, 'sensor', {
            'sensor': {
                'platform': 'api_streams',
            }
        })

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '0'

    log.debug('WS %s: %s', id(log), 'Connected')
    yield from hass.async_block_till_done()

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '1'

    log.debug('WS %s: %s', id(log), 'Connected')
    yield from hass.async_block_till_done()

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '2'

    log.debug('WS %s: %s', id(log), 'Closed connection')
    yield from hass.async_block_till_done()

    state = hass.states.get('sensor.connected_clients')
    assert state.state == '1'
