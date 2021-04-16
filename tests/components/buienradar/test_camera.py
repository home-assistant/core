"""The tests for generic camera component."""
import asyncio
from contextlib import suppress

from aiohttp.client_exceptions import ClientResponseError

from homeassistant.const import HTTP_INTERNAL_SERVER_ERROR
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

# An infinitesimally small time-delta.
EPSILON_DELTA = 0.0000000001


def radar_map_url(dim: int = 512, country_code: str = "NL") -> str:
    """Build map url, defaulting to 512 wide (as in component)."""
    return f"https://api.buienradar.nl/image/1.0/RadarMap{country_code}?w={dim}&h={dim}"


async def test_fetching_url_and_caching(aioclient_mock, hass, hass_client):
    """Test that it fetches the given url."""
    aioclient_mock.get(radar_map_url(), text="hello world")

    await async_setup_component(
        hass, "camera", {"camera": {"name": "config_test", "platform": "buienradar"}}
    )
    await hass.async_block_till_done()

    client = await hass_client()

    resp = await client.get("/api/camera_proxy/camera.config_test")

    assert resp.status == 200
    assert aioclient_mock.call_count == 1
    body = await resp.text()
    assert body == "hello world"

    # default delta is 600s -> should be the same when calling immediately
    # afterwards.

    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert aioclient_mock.call_count == 1


async def test_expire_delta(aioclient_mock, hass, hass_client):
    """Test that the cache expires after delta."""
    aioclient_mock.get(radar_map_url(), text="hello world")

    await async_setup_component(
        hass,
        "camera",
        {
            "camera": {
                "name": "config_test",
                "platform": "buienradar",
                "delta": EPSILON_DELTA,
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client()

    resp = await client.get("/api/camera_proxy/camera.config_test")

    assert resp.status == 200
    assert aioclient_mock.call_count == 1
    body = await resp.text()
    assert body == "hello world"

    await asyncio.sleep(EPSILON_DELTA)
    # tiny delta has passed -> should immediately call again
    resp = await client.get("/api/camera_proxy/camera.config_test")
    assert aioclient_mock.call_count == 2


async def test_only_one_fetch_at_a_time(aioclient_mock, hass, hass_client):
    """Test that it fetches with only one request at the same time."""
    aioclient_mock.get(radar_map_url(), text="hello world")

    await async_setup_component(
        hass, "camera", {"camera": {"name": "config_test", "platform": "buienradar"}}
    )
    await hass.async_block_till_done()

    client = await hass_client()

    resp_1 = client.get("/api/camera_proxy/camera.config_test")
    resp_2 = client.get("/api/camera_proxy/camera.config_test")

    resp = await resp_1
    resp_2 = await resp_2

    assert (await resp.text()) == (await resp_2.text())

    assert aioclient_mock.call_count == 1


async def test_dimension(aioclient_mock, hass, hass_client):
    """Test that it actually adheres to the dimension."""
    aioclient_mock.get(radar_map_url(700), text="hello world")

    await async_setup_component(
        hass,
        "camera",
        {"camera": {"name": "config_test", "platform": "buienradar", "dimension": 700}},
    )
    await hass.async_block_till_done()

    client = await hass_client()

    await client.get("/api/camera_proxy/camera.config_test")

    assert aioclient_mock.call_count == 1


async def test_belgium_country(aioclient_mock, hass, hass_client):
    """Test that it actually adheres to another country like Belgium."""
    aioclient_mock.get(radar_map_url(country_code="BE"), text="hello world")

    await async_setup_component(
        hass,
        "camera",
        {
            "camera": {
                "name": "config_test",
                "platform": "buienradar",
                "country_code": "BE",
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client()

    await client.get("/api/camera_proxy/camera.config_test")

    assert aioclient_mock.call_count == 1


async def test_failure_response_not_cached(aioclient_mock, hass, hass_client):
    """Test that it does not cache a failure response."""
    aioclient_mock.get(radar_map_url(), text="hello world", status=401)

    await async_setup_component(
        hass, "camera", {"camera": {"name": "config_test", "platform": "buienradar"}}
    )
    await hass.async_block_till_done()

    client = await hass_client()

    await client.get("/api/camera_proxy/camera.config_test")
    await client.get("/api/camera_proxy/camera.config_test")

    assert aioclient_mock.call_count == 2


async def test_last_modified_updates(aioclient_mock, hass, hass_client):
    """Test that it does respect HTTP not modified."""
    # Build Last-Modified header value
    now = dt_util.utcnow()
    last_modified = now.strftime("%a, %d %m %Y %H:%M:%S GMT")

    aioclient_mock.get(
        radar_map_url(),
        text="hello world",
        status=200,
        headers={"Last-Modified": last_modified},
    )

    await async_setup_component(
        hass,
        "camera",
        {
            "camera": {
                "name": "config_test",
                "platform": "buienradar",
                "delta": EPSILON_DELTA,
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client()

    resp_1 = await client.get("/api/camera_proxy/camera.config_test")
    # It is not possible to check if header was sent.
    assert aioclient_mock.call_count == 1

    await asyncio.sleep(EPSILON_DELTA)

    # Content has expired, change response to a 304 NOT MODIFIED, which has no
    # text, i.e. old value should be kept
    aioclient_mock.clear_requests()
    # mock call count is now reset as well:
    assert aioclient_mock.call_count == 0

    aioclient_mock.get(radar_map_url(), text=None, status=304)

    resp_2 = await client.get("/api/camera_proxy/camera.config_test")
    assert aioclient_mock.call_count == 1

    assert (await resp_1.read()) == (await resp_2.read())


async def test_retries_after_error(aioclient_mock, hass, hass_client):
    """Test that it does retry after an error instead of caching."""
    await async_setup_component(
        hass, "camera", {"camera": {"name": "config_test", "platform": "buienradar"}}
    )
    await hass.async_block_till_done()

    client = await hass_client()

    aioclient_mock.get(radar_map_url(), text=None, status=HTTP_INTERNAL_SERVER_ERROR)

    # A 404 should not return data and throw:
    with suppress(ClientResponseError):
        await client.get("/api/camera_proxy/camera.config_test")

    assert aioclient_mock.call_count == 1

    # Change the response to a 200
    aioclient_mock.clear_requests()
    aioclient_mock.get(radar_map_url(), text="DEADBEEF")

    assert aioclient_mock.call_count == 0

    # http error should not be cached, immediate retry.
    resp_2 = await client.get("/api/camera_proxy/camera.config_test")
    assert aioclient_mock.call_count == 1

    # Binary text can not be added as body to `aioclient_mock.get(text=...)`,
    # while `resp.read()` returns bytes, encode the value.
    assert (await resp_2.read()) == b"DEADBEEF"
