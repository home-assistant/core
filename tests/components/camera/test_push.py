"""The tests for generic camera component."""
import io

from datetime import timedelta

from homeassistant import core as ha
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.components.http.auth import setup_auth


async def test_bad_posting(aioclient_mock, hass, aiohttp_client):
    """Test that posting to wrong api endpoint fails."""
    await async_setup_component(hass, 'camera', {
        'camera': {
            'platform': 'push',
            'name': 'config_test',
            'token': '12345678'
        }})
    client = await aiohttp_client(hass.http.app)

    # missing file
    resp = await client.post('/api/camera_push/camera.config_test')
    assert resp.status == 400

    # wrong entity
    files = {'image': io.BytesIO(b'fake')}
    resp = await client.post('/api/camera_push/camera.wrong', data=files)
    assert resp.status == 404


async def test_cases_with_no_auth(aioclient_mock, hass, aiohttp_client):
    """Test cases where aiohttp_client is not auth."""
    await async_setup_component(hass, 'camera', {
        'camera': {
            'platform': 'push',
            'name': 'config_test',
            'token': '12345678'
        }})

    setup_auth(hass.http.app, [], True, api_password=None)
    client = await aiohttp_client(hass.http.app)

    # wrong token
    files = {'image': io.BytesIO(b'fake')}
    resp = await client.post('/api/camera_push/camera.config_test?token=1234',
                             data=files)
    assert resp.status == 401

    # right token
    files = {'image': io.BytesIO(b'fake')}
    resp = await client.post(
        '/api/camera_push/camera.config_test?token=12345678',
        data=files)
    assert resp.status == 200


async def test_no_auth_no_token(aioclient_mock, hass, aiohttp_client):
    """Test cases where aiohttp_client is not auth."""
    await async_setup_component(hass, 'camera', {
        'camera': {
            'platform': 'push',
            'name': 'config_test',
        }})

    setup_auth(hass.http.app, [], True, api_password=None)
    client = await aiohttp_client(hass.http.app)

    # no token
    files = {'image': io.BytesIO(b'fake')}
    resp = await client.post('/api/camera_push/camera.config_test',
                             data=files)
    assert resp.status == 401

    # fake token
    files = {'image': io.BytesIO(b'fake')}
    resp = await client.post(
        '/api/camera_push/camera.config_test?token=12345678',
        data=files)
    assert resp.status == 401


async def test_posting_url(hass, aiohttp_client):
    """Test that posting to api endpoint works."""
    await async_setup_component(hass, 'camera', {
        'camera': {
            'platform': 'push',
            'name': 'config_test',
            'token': '12345678'
        }})

    client = await aiohttp_client(hass.http.app)
    files = {'image': io.BytesIO(b'fake')}

    # initial state
    camera_state = hass.states.get('camera.config_test')
    assert camera_state.state == 'idle'

    # post image
    resp = await client.post(
        '/api/camera_push/camera.config_test?token=12345678',
        data=files)
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
