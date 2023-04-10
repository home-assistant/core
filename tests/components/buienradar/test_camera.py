"""The tests for generic camera component."""
import asyncio
from contextlib import suppress
import copy
from http import HTTPStatus

from aiohttp.client_exceptions import ClientResponseError

from homeassistant.components.buienradar.const import CONF_COUNTRY, CONF_DELTA, DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

# An infinitesimally small time-delta.
EPSILON_DELTA = 0.0000000001

TEST_LATITUDE = 51.5288504
TEST_LONGITUDE = 5.4002156

TEST_CFG_DATA = {CONF_LATITUDE: TEST_LATITUDE, CONF_LONGITUDE: TEST_LONGITUDE}


def radar_map_url(country_code: str = "NL") -> str:
    """Build map URL."""
    return f"https://api.buienradar.nl/image/1.0/RadarMap{country_code}?w=700&h=700"


async def _setup_config_entry(hass, entry):
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        domain="camera",
        platform="buienradar",
        unique_id=f"{TEST_LATITUDE:2.6f}{TEST_LONGITUDE:2.6f}",
        config_entry=entry,
        original_name="Buienradar",
    )
    await hass.async_block_till_done()

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_fetching_url_and_caching(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that it fetches the given url."""
    aioclient_mock.get(radar_map_url(), text="hello world")

    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA)

    mock_entry.add_to_hass(hass)

    await _setup_config_entry(hass, mock_entry)

    client = await hass_client()

    resp = await client.get("/api/camera_proxy/camera.buienradar_51_5288505_400216")

    assert resp.status == HTTPStatus.OK
    assert aioclient_mock.call_count == 1
    body = await resp.text()
    assert body == "hello world"

    # default delta is 600s -> should be the same when calling immediately
    # afterwards.

    resp = await client.get("/api/camera_proxy/camera.buienradar_51_5288505_400216")
    assert aioclient_mock.call_count == 1


async def test_expire_delta(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that the cache expires after delta."""
    aioclient_mock.get(radar_map_url(), text="hello world")

    options = {CONF_DELTA: EPSILON_DELTA}

    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA, options=options
    )

    mock_entry.add_to_hass(hass)

    await _setup_config_entry(hass, mock_entry)

    client = await hass_client()

    resp = await client.get("/api/camera_proxy/camera.buienradar_51_5288505_400216")

    assert resp.status == HTTPStatus.OK
    assert aioclient_mock.call_count == 1
    body = await resp.text()
    assert body == "hello world"

    await asyncio.sleep(EPSILON_DELTA)
    # tiny delta has passed -> should immediately call again
    resp = await client.get("/api/camera_proxy/camera.buienradar_51_5288505_400216")
    assert aioclient_mock.call_count == 2


async def test_only_one_fetch_at_a_time(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that it fetches with only one request at the same time."""
    aioclient_mock.get(radar_map_url(), text="hello world")

    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA)

    mock_entry.add_to_hass(hass)

    await _setup_config_entry(hass, mock_entry)

    client = await hass_client()

    resp_1 = client.get("/api/camera_proxy/camera.buienradar_51_5288505_400216")
    resp_2 = client.get("/api/camera_proxy/camera.buienradar_51_5288505_400216")

    resp = await resp_1
    resp_2 = await resp_2

    assert (await resp.text()) == (await resp_2.text())

    assert aioclient_mock.call_count == 1


async def test_belgium_country(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that it actually adheres to another country like Belgium."""
    aioclient_mock.get(radar_map_url(country_code="BE"), text="hello world")

    data = copy.deepcopy(TEST_CFG_DATA)
    data[CONF_COUNTRY] = "BE"

    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=data)

    mock_entry.add_to_hass(hass)

    await _setup_config_entry(hass, mock_entry)

    client = await hass_client()

    await client.get("/api/camera_proxy/camera.buienradar_51_5288505_400216")

    assert aioclient_mock.call_count == 1


async def test_failure_response_not_cached(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that it does not cache a failure response."""
    aioclient_mock.get(radar_map_url(), text="hello world", status=401)

    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA)

    mock_entry.add_to_hass(hass)

    await _setup_config_entry(hass, mock_entry)

    client = await hass_client()

    await client.get("/api/camera_proxy/camera.buienradar_51_5288505_400216")
    await client.get("/api/camera_proxy/camera.buienradar_51_5288505_400216")

    assert aioclient_mock.call_count == 2


async def test_last_modified_updates(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
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

    options = {CONF_DELTA: EPSILON_DELTA}

    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA, options=options
    )

    mock_entry.add_to_hass(hass)

    await _setup_config_entry(hass, mock_entry)

    client = await hass_client()

    resp_1 = await client.get("/api/camera_proxy/camera.buienradar_51_5288505_400216")
    # It is not possible to check if header was sent.
    assert aioclient_mock.call_count == 1

    await asyncio.sleep(EPSILON_DELTA)

    # Content has expired, change response to a 304 NOT MODIFIED, which has no
    # text, i.e. old value should be kept
    aioclient_mock.clear_requests()
    # mock call count is now reset as well:
    assert aioclient_mock.call_count == 0

    aioclient_mock.get(radar_map_url(), text=None, status=304)

    resp_2 = await client.get("/api/camera_proxy/camera.buienradar_51_5288505_400216")
    assert aioclient_mock.call_count == 1

    assert (await resp_1.read()) == (await resp_2.read())


async def test_retries_after_error(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that it does retry after an error instead of caching."""
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA)

    mock_entry.add_to_hass(hass)

    await _setup_config_entry(hass, mock_entry)

    client = await hass_client()

    aioclient_mock.get(
        radar_map_url(), text=None, status=HTTPStatus.INTERNAL_SERVER_ERROR
    )

    # A 404 should not return data and throw:
    with suppress(ClientResponseError):
        await client.get("/api/camera_proxy/camera.buienradar_51_5288505_400216")

    assert aioclient_mock.call_count == 1

    # Change the response to a 200
    aioclient_mock.clear_requests()
    aioclient_mock.get(radar_map_url(), text="DEADBEEF")

    assert aioclient_mock.call_count == 0

    # http error should not be cached, immediate retry.
    resp_2 = await client.get("/api/camera_proxy/camera.buienradar_51_5288505_400216")
    assert aioclient_mock.call_count == 1

    # Binary text cannot be added as body to `aioclient_mock.get(text=...)`,
    # while `resp.read()` returns bytes, encode the value.
    assert (await resp_2.read()) == b"DEADBEEF"
