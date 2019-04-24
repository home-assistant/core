"""The tests for generic camera component."""
import asyncio

from homeassistant.setup import async_setup_component


def radar_map_url(dim: int = 512) -> str:
    """Build map url, defaulting to 512 wide (as in component)."""
    return ("https://api.buienradar.nl/"
            "image/1.0/RadarMapNL?w={dim}&h={dim}").format(dim=dim)


@asyncio.coroutine
def test_fetching_url_and_caching(aioclient_mock, hass, hass_client):
    """Test that it fetches the given url."""
    aioclient_mock.get(radar_map_url(), text='hello world')

    yield from async_setup_component(hass, 'camera', {
        'camera': {
            'name': 'config_test',
            'platform': 'buienradar',
        }})

    client = yield from hass_client()

    resp = yield from client.get('/api/camera_proxy/camera.config_test')

    assert resp.status == 200
    assert aioclient_mock.call_count == 1
    body = yield from resp.text()
    assert body == 'hello world'

    # default interval is 600s -> should be the same when calling immediately
    # afterwards.

    resp = yield from client.get('/api/camera_proxy/camera.config_test')
    assert aioclient_mock.call_count == 1


async def test_expire_interval(aioclient_mock, hass, hass_client):
    """Test that the cache expires after interval."""
    aioclient_mock.get(radar_map_url(), text='hello world')

    interval = 0.0000000001

    await async_setup_component(hass, 'camera', {
        'camera': {
            'name': 'config_test',
            'platform': 'buienradar',
            'interval': interval,
        }})

    client = await hass_client()

    resp = await client.get('/api/camera_proxy/camera.config_test')

    assert resp.status == 200
    assert aioclient_mock.call_count == 1
    body = await resp.text()
    assert body == 'hello world'

    await asyncio.sleep(interval)
    # interval has passed -> should immediately call again
    resp = await client.get('/api/camera_proxy/camera.config_test')
    assert aioclient_mock.call_count == 2


@asyncio.coroutine
def test_only_one_fetch_at_a_time(aioclient_mock, hass, hass_client):
    """Test that it fetches with only one request at the same time."""
    aioclient_mock.get(radar_map_url(), text='hello world')

    yield from async_setup_component(hass, 'camera', {
        'camera': {
            'name': 'config_test',
            'platform': 'buienradar',
        }})

    client = yield from hass_client()

    resp_1 = client.get('/api/camera_proxy/camera.config_test')
    resp_2 = client.get('/api/camera_proxy/camera.config_test')

    resp = yield from resp_1
    resp_2 = yield from resp_2

    assert (yield from resp.text()) == (yield from resp_2.text())

    assert aioclient_mock.call_count == 1


@asyncio.coroutine
def test_dimension(aioclient_mock, hass, hass_client):
    """Test that it actually adheres to the dimension."""
    aioclient_mock.get(radar_map_url(700), text='hello world')

    yield from async_setup_component(hass, 'camera', {
        'camera': {
            'name': 'config_test',
            'platform': 'buienradar',
            'dimension': 700,
        }})

    client = yield from hass_client()

    yield from client.get('/api/camera_proxy/camera.config_test')

    assert aioclient_mock.call_count == 1


@asyncio.coroutine
def test_failure_response_not_cached(aioclient_mock, hass, hass_client):
    """Test that it does not cache a failure response."""
    aioclient_mock.get(radar_map_url(), text='hello world', status=401)

    yield from async_setup_component(hass, 'camera', {
        'camera': {
            'name': 'config_test',
            'platform': 'buienradar',
        }})

    client = yield from hass_client()

    yield from client.get('/api/camera_proxy/camera.config_test')
    yield from client.get('/api/camera_proxy/camera.config_test')

    assert aioclient_mock.call_count == 2
