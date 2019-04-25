"""The tests for generic camera component."""
import asyncio

from homeassistant.util import dt as dt_util

from homeassistant.setup import async_setup_component

# An infinitesimally small time-delta.
EPSILON_DELTA = 0.0000000001


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

    # default delta is 600s -> should be the same when calling immediately
    # afterwards.

    resp = yield from client.get('/api/camera_proxy/camera.config_test')
    assert aioclient_mock.call_count == 1


@asyncio.coroutine
def test_expire_delta(aioclient_mock, hass, hass_client):
    """Test that the cache expires after delta."""
    aioclient_mock.get(radar_map_url(), text='hello world')

    yield from async_setup_component(hass, 'camera', {
        'camera': {
            'name': 'config_test',
            'platform': 'buienradar',
            'delta': EPSILON_DELTA,
        }})

    client = yield from hass_client()

    resp = yield from client.get('/api/camera_proxy/camera.config_test')

    assert resp.status == 200
    assert aioclient_mock.call_count == 1
    body = yield from resp.text()
    assert body == 'hello world'

    yield from asyncio.sleep(EPSILON_DELTA)
    # tiny delta has passed -> should immediately call again
    resp = yield from client.get('/api/camera_proxy/camera.config_test')
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


@asyncio.coroutine
def test_last_modified_updates(aioclient_mock, hass, hass_client):
    """Test that it does respect HTTP not modified."""
    # Build Last-Modified header value
    now = dt_util.utcnow()
    last_modified = now.strftime("%a, %d %m %Y %H:%M:%S GMT")

    aioclient_mock.get(radar_map_url(), text='hello world', status=200,
                       headers={
                           'Last-Modified':  last_modified,
                       })

    yield from async_setup_component(hass, 'camera', {
        'camera': {
            'name': 'config_test',
            'platform': 'buienradar',
            'delta': EPSILON_DELTA,
        }})

    client = yield from hass_client()

    resp_1 = yield from client.get('/api/camera_proxy/camera.config_test')
    # It is not possible to check if header was sent.
    assert aioclient_mock.call_count == 1

    yield from asyncio.sleep(EPSILON_DELTA)

    # Content has expired, change response to a 304 NOT MODIFIED, which has no
    # text, i.e. old value should be kept
    aioclient_mock.clear_requests()
    # mock call count is now reset as well:
    assert aioclient_mock.call_count == 0

    aioclient_mock.get(radar_map_url(), text=None, status=304)

    resp_2 = yield from client.get('/api/camera_proxy/camera.config_test')
    assert aioclient_mock.call_count == 1

    assert (yield from resp_1.read()) == (yield from resp_2.read())
