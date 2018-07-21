"""The tests for generic camera component."""
import io

from datetime import timedelta

from homeassistant import core as ha
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from tests.components.auth import async_setup_auth


async def test_bad_posting(aioclient_mock, hass, aiohttp_client):
    """Test that posting to wrong api endpoint fails."""
    await async_setup_component(hass, 'camera', {
        'camera': {
            'platform': 'push',
            'name': 'config_test',
        }})

    client = await async_setup_auth(hass, aiohttp_client)

    # missing file
    resp = await client.post('/api/camera_push/camera.config_test')
    assert resp.status == 400

    files = {'image': io.BytesIO(b'fake')}

    # wrong entity
    resp = await client.post('/api/camera_push/camera.wrong', data=files)
    assert resp.status == 400


async def test_posting_url(aioclient_mock, hass, aiohttp_client):
    """Test that posting to api endpoint works."""
    await async_setup_component(hass, 'camera', {
        'camera': {
            'platform': 'push',
            'name': 'config_test',
        }})

    client = await async_setup_auth(hass, aiohttp_client)
    files = {'image': io.BytesIO(b'fake')}

    # initial state
    camera_state = hass.states.get('camera.config_test')
    assert camera_state.state == 'idle'

    # post image
    resp = await client.post('/api/camera_push/camera.config_test', data=files)
    assert resp.status == 200

    # state recording
    camera_state = hass.states.get('camera.config_test')
    assert camera_state.state == 'recording'

    # await timeout
    shifted_time = dt_util.utcnow() + timedelta(seconds=15)
    hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: shifted_time})
    await hass.async_block_till_done()

    # back to initial state
    camera_state = hass.states.get('camera.config_test')
    assert camera_state.state == 'idle'
