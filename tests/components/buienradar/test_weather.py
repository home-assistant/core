"""The tests for the buienradar weather component."""

from http import HTTPStatus

from buienradar.urls import JSON_FEED_URL, json_precipitation_forecast_url
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.buienradar.const import DOMAIN
from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_CFG_DATA = {CONF_LATITUDE: 51.5288504, CONF_LONGITUDE: 5.4002156}
TEST_CFG_DATA_UNKNOWN_CONDITION = {CONF_LATITUDE: 51.5, CONF_LONGITUDE: 6.2}
TEST_CFG_DATA_UNKNOWN_ATTRIBUTON = {CONF_LATITUDE: 52.07, CONF_LONGITUDE: 5.88}
TEST_ICON_URL = "https://www.buienradar.nl/resources/images/icons/weather/30x30/CC.png"


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


async def test_fetch_json_data(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fetching json and rain data.

    The iconurl in the returned data is lowercase; workaround not applied.
    """
    aioclient_mock.get(
        JSON_FEED_URL,
        status=HTTPStatus.OK,
        text=load_fixture("buienradar.json", DOMAIN),
    )
    aioclient_mock.get(
        json_precipitation_forecast_url(
            TEST_CFG_DATA[CONF_LATITUDE], TEST_CFG_DATA[CONF_LONGITUDE]
        ),
        status=HTTPStatus.OK,
        text=load_fixture("raindata.txt", DOMAIN),
    )
    # this simulates that the iconurl in the returned data is correct and workaround need not be applied:
    aioclient_mock.get(TEST_ICON_URL, status=HTTPStatus.NOT_FOUND)

    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="test_fetch_json_data", data=TEST_CFG_DATA
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.buienradar")
    assert state
    assert state.state == "cloudy"
    assert state.attributes == snapshot


@pytest.mark.parametrize(
    ("service"),
    [SERVICE_GET_FORECASTS],
)
async def test_fetch_json_data_forecast(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    service,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fetching json and rain data.

    The iconurl in the returned data is lowercase; workaround not applied.
    """
    aioclient_mock.get(
        JSON_FEED_URL,
        status=HTTPStatus.OK,
        text=load_fixture("buienradar.json", DOMAIN),
    )
    aioclient_mock.get(
        json_precipitation_forecast_url(
            TEST_CFG_DATA[CONF_LATITUDE], TEST_CFG_DATA[CONF_LONGITUDE]
        ),
        status=HTTPStatus.OK,
        text=load_fixture("raindata.txt", DOMAIN),
    )
    # this simulates that the iconurl in the returned data is correct and workaround need not be applied:
    aioclient_mock.get(TEST_ICON_URL, status=HTTPStatus.NOT_FOUND)

    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="test_fetch_json_data", data=TEST_CFG_DATA
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    # test forecast data
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {
            "entity_id": "weather.buienradar",
            "type": "daily",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


async def test_fetch_json_data_workaround(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Fetching json and rain data and fix the iconrl filename being incorrect.

    This is to test the case where buienradar iconurl has a lowercase image filename, but the server serves the image in uppercase.
    """
    aioclient_mock.get(
        JSON_FEED_URL,
        status=HTTPStatus.OK,
        text=load_fixture("buienradar.json", DOMAIN),
    )
    aioclient_mock.get(
        json_precipitation_forecast_url(
            TEST_CFG_DATA[CONF_LATITUDE], TEST_CFG_DATA[CONF_LONGITUDE]
        ),
        status=HTTPStatus.OK,
        text=load_fixture("raindata.txt", DOMAIN),
    )
    aioclient_mock.get(TEST_ICON_URL, status=HTTPStatus.OK)

    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="test_fetch_json_data_workaround", data=TEST_CFG_DATA
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.buienradar")
    assert state
    assert state.state == "cloudy"
    assert state.attributes == snapshot


@pytest.mark.parametrize(
    ("service"),
    [SERVICE_GET_FORECASTS],
)
async def test_fetch_json_data_forecast_workaround(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    service,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fetching json and rain data.

    The iconurl in the returned data is lowercase; workaround is applied.
    """
    aioclient_mock.get(
        JSON_FEED_URL,
        status=HTTPStatus.OK,
        text=load_fixture("buienradar.json", DOMAIN),
    )
    aioclient_mock.get(
        json_precipitation_forecast_url(
            TEST_CFG_DATA[CONF_LATITUDE], TEST_CFG_DATA[CONF_LONGITUDE]
        ),
        status=HTTPStatus.OK,
        text=load_fixture("raindata.txt", DOMAIN),
    )
    # this simulates that the iconurl in the returned data is correct and workaround need not be applied:
    aioclient_mock.get(TEST_ICON_URL, status=HTTPStatus.OK)

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_fetch_json_data_forecast_workaround",
        data=TEST_CFG_DATA,
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    # test forecast data
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {
            "entity_id": "weather.buienradar",
            "type": "daily",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


async def test_fetch_json_data_noforecasts(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fetching json and rain data without forecast data."""

    aioclient_mock.get(
        JSON_FEED_URL,
        status=HTTPStatus.OK,
        text=load_fixture("buienradar_nofc.json", DOMAIN),
    )
    aioclient_mock.get(
        json_precipitation_forecast_url(
            TEST_CFG_DATA[CONF_LATITUDE], TEST_CFG_DATA[CONF_LONGITUDE]
        ),
        status=HTTPStatus.OK,
        text=load_fixture("raindata.txt", DOMAIN),
    )
    # this simulates that the iconurl in the returned data is correct and workaround need not be applied:
    aioclient_mock.get(TEST_ICON_URL, status=HTTPStatus.NOT_FOUND)

    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="test_fetch_json_data", data=TEST_CFG_DATA
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.buienradar")
    assert state
    assert state.state == "cloudy"
    assert state.attributes == snapshot


async def test_unknown_condition(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fetching json and rain data with an unknown condition code."""
    aioclient_mock.get(
        JSON_FEED_URL,
        status=HTTPStatus.OK,
        text=load_fixture("buienradar.json", DOMAIN),
    )
    aioclient_mock.get(
        json_precipitation_forecast_url(
            TEST_CFG_DATA_UNKNOWN_CONDITION[CONF_LATITUDE],
            TEST_CFG_DATA_UNKNOWN_CONDITION[CONF_LONGITUDE],
        ),
        status=HTTPStatus.OK,
        text=load_fixture("raindata.txt", DOMAIN),
    )
    # this simulates that the iconurl in the returned data is correct and workaround need not be applied:
    aioclient_mock.get(TEST_ICON_URL, status=HTTPStatus.NOT_FOUND)

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_fetch_json_data",
        data=TEST_CFG_DATA_UNKNOWN_CONDITION,
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.buienradar")
    assert state
    assert state.state == "unknown"
    assert state.attributes == snapshot


async def test_fetch_no_raindata(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fetching json and rain data fails."""

    aioclient_mock.get(
        JSON_FEED_URL,
        status=HTTPStatus.OK,
        text=load_fixture("buienradar.json", DOMAIN),
    )
    aioclient_mock.get(
        json_precipitation_forecast_url(
            TEST_CFG_DATA[CONF_LATITUDE], TEST_CFG_DATA[CONF_LONGITUDE]
        ),
        status=HTTPStatus.BAD_REQUEST,
    )
    # this simulates that the iconurl in the returned data is correct and workaround need not be applied:
    aioclient_mock.get(TEST_ICON_URL, status=HTTPStatus.NOT_FOUND)

    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="test_fetch_json_data", data=TEST_CFG_DATA
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.buienradar")
    assert state
    assert state.state == "unknown"
    assert state.attributes == snapshot


async def test_fetch_no_json_data(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fetching non-json data."""

    aioclient_mock.get(
        JSON_FEED_URL,
        status=HTTPStatus.OK,
        text=load_fixture("buienradar_nojson.txt", DOMAIN),
    )
    aioclient_mock.get(
        json_precipitation_forecast_url(
            TEST_CFG_DATA[CONF_LATITUDE], TEST_CFG_DATA[CONF_LONGITUDE]
        ),
        status=HTTPStatus.OK,
        text=load_fixture("raindata.txt", DOMAIN),
    )
    # this simulates that the iconurl in the returned data is correct and workaround need not be applied:
    aioclient_mock.get(TEST_ICON_URL, status=HTTPStatus.NOT_FOUND)

    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="test_fetch_json_data", data=TEST_CFG_DATA
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.buienradar")
    assert state
    assert state.state == "unknown"
    assert state.attributes == snapshot


async def test_fetch_unknow_attribution_values(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fetching data withunparsable attribution values."""

    aioclient_mock.get(
        JSON_FEED_URL,
        status=HTTPStatus.OK,
        text=load_fixture("buienradar.json", DOMAIN),
    )
    aioclient_mock.get(
        json_precipitation_forecast_url(
            TEST_CFG_DATA_UNKNOWN_ATTRIBUTON[CONF_LATITUDE],
            TEST_CFG_DATA_UNKNOWN_ATTRIBUTON[CONF_LONGITUDE],
        ),
        status=HTTPStatus.OK,
        text=load_fixture("raindata.txt", DOMAIN),
    )
    # this simulates that the iconurl in the returned data is correct and workaround need not be applied:
    aioclient_mock.get(TEST_ICON_URL, status=HTTPStatus.NOT_FOUND)

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_fetch_json_data",
        data=TEST_CFG_DATA_UNKNOWN_ATTRIBUTON,
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.buienradar")
    assert state == snapshot
    assert state.attributes == snapshot
