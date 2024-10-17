"""The tests for the buienradar weather component."""

from http import HTTPStatus

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.buienradar.const import DOMAIN
from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_LATITUDE, CONF_LONGITUDE, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture, load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_CFG_DATA = {CONF_LATITUDE: 51.5288504, CONF_LONGITUDE: 5.4002156}
TEST_CFG_INVALID_COORDINATES = {CONF_LATITUDE: None, CONF_LONGITUDE: None}
TEST_CFG_INVALID_DATA = {CONF_LATITUDE: 53.45, CONF_LONGITUDE: 6.42}
ENTITY_ID = "weather.buienradar"


async def test_smoke_test_setup_component(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Smoke test for successfully set-up with default config."""
    aioclient_mock.get(
        "https://data.buienradar.nl/2.0/feed/json", status=HTTPStatus.NOT_FOUND
    )

    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.buienradar")
    assert state.state == "unknown"


async def test_smoke_test_setup_component_no_coordinates(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Smoke test for set-up without valid coordinates."""
    aioclient_mock.get(
        "https://data.buienradar.nl/2.0/feed/json", status=HTTPStatus.NOT_FOUND
    )

    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_INVALID_COORDINATES
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.buienradar")
    assert state is None


async def test_attribute_values(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for fetching (mocked) weather data and checking attribute values."""
    brJson = load_json_object_fixture("buienradar.json", DOMAIN)
    raindata = load_fixture("raindata.txt", DOMAIN)
    aioclient_mock.get(
        "https://data.buienradar.nl/2.0/feed/json", status=HTTPStatus.OK, json=brJson
    )
    aioclient_mock.get(
        f"https://gpsgadget.buienradar.nl/data/raintext?lat={TEST_CFG_DATA[CONF_LATITUDE]:.2f}&lon={TEST_CFG_DATA[CONF_LONGITUDE]:.1f}",
        status=HTTPStatus.OK,
        text=raindata,
    )

    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.buienradar")
    assert state == snapshot


async def test_get_forecast(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for fetching (mocked) weather data and checking forecast values."""
    brJson = load_json_object_fixture("buienradar.json", DOMAIN)
    raindata = load_fixture("raindata.txt", DOMAIN)
    aioclient_mock.get(
        "https://data.buienradar.nl/2.0/feed/json", status=HTTPStatus.OK, json=brJson
    )
    aioclient_mock.get(
        f"https://gpsgadget.buienradar.nl/data/raintext?lat={TEST_CFG_DATA[CONF_LATITUDE]:.2f}&lon={TEST_CFG_DATA[CONF_LONGITUDE]:.1f}",
        status=HTTPStatus.OK,
        text=raindata,
    )

    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA)
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {ATTR_ENTITY_ID: ENTITY_ID, CONF_TYPE: "daily"},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()

    assert response == snapshot


async def test_attribute_values_invalid_data(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for fetching (mocked) weather data (with some values not present/invalid) to test attribute values."""
    brJson = load_json_object_fixture("buienradar.json", DOMAIN)
    raindata = load_fixture("raindata.txt", DOMAIN)
    aioclient_mock.get(
        "https://data.buienradar.nl/2.0/feed/json", status=HTTPStatus.OK, json=brJson
    )
    aioclient_mock.get(
        f"https://gpsgadget.buienradar.nl/data/raintext?lat={TEST_CFG_INVALID_DATA[CONF_LATITUDE]:.2f}&lon={TEST_CFG_INVALID_DATA[CONF_LONGITUDE]:.2f}",
        status=HTTPStatus.OK,
        text=raindata,
    )

    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_INVALID_DATA
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.buienradar")
    assert state == snapshot


async def test_smoke_test_no_forecasts(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for fetching (mocked) weather data (with forecast data missing) to test attribute values."""
    brJson = load_json_object_fixture("buienradarNoForecast.json", DOMAIN)
    raindata = load_fixture("raindata.txt", DOMAIN)
    aioclient_mock.get(
        "https://data.buienradar.nl/2.0/feed/json", status=HTTPStatus.OK, json=brJson
    )
    aioclient_mock.get(
        f"https://gpsgadget.buienradar.nl/data/raintext?lat={TEST_CFG_INVALID_DATA[CONF_LATITUDE]:.2f}&lon={TEST_CFG_INVALID_DATA[CONF_LONGITUDE]:.2f}",
        status=HTTPStatus.OK,
        text=raindata,
    )

    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_INVALID_DATA
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.buienradar")
    assert state == snapshot
