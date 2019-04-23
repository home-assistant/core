"""Tests for the cloud binary sensor."""
from unittest.mock import Mock

from homeassistant.setup import async_setup_component
from homeassistant.components.cloud.const import DISPATCHER_REMOTE_UPDATE


async def test_remote_connection_sensor(hass):
    """Test the remote connection sensor."""
    from homeassistant.components.cloud import binary_sensor as bin_sensor
    bin_sensor.WAIT_UNTIL_CHANGE = 0

    assert await async_setup_component(hass, 'cloud', {'cloud': {}})
    cloud = hass.data['cloud'] = Mock()
    cloud.remote.certificate = None
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.remote_ui')
    assert state is not None
    assert state.state == 'unavailable'

    cloud.remote.is_connected = False
    cloud.remote.certificate = object()
    hass.helpers.dispatcher.async_dispatcher_send(DISPATCHER_REMOTE_UPDATE, {})
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.remote_ui')
    assert state.state == 'off'

    cloud.remote.is_connected = True
    hass.helpers.dispatcher.async_dispatcher_send(DISPATCHER_REMOTE_UPDATE, {})
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.remote_ui')
    assert state.state == 'on'
