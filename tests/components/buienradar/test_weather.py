"""The tests for the buienradar weather component."""

from http import HTTPStatus

from homeassistant.components.buienradar.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture, load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_CFG_DATA = {CONF_LATITUDE: 51.5288504, CONF_LONGITUDE: 5.4002156}
TEST_CFG_INVALID_COORDINATES = {CONF_LATITUDE: None, CONF_LONGITUDE: None}
TEST_CFG_INVALID_DATA = {CONF_LATITUDE: 53.45, CONF_LONGITUDE: 6.42}


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
    """Smoke test for successfully set-up with default config."""
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


async def test_smoke_test_data(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Smoke test for successfully set-up with default config and check fetcheddata."""
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
    assert state.state == "cloudy"

    assert state.attributes["temperature"] == 20.4
    assert state.attributes["apparent_temperature"] == 20.5
    assert state.attributes["temperature_unit"] == "°C"
    assert state.attributes["humidity"] == 76.0
    assert state.attributes["pressure"] == 1020.0
    assert state.attributes["pressure_unit"] == "hPa"
    assert state.attributes["wind_bearing"] == 38
    assert state.attributes["wind_gust_speed"] == 23.4
    assert state.attributes["wind_speed"] == 14.4
    assert state.attributes["wind_speed_unit"] == "km/h"
    assert state.attributes["visibility"] == 32.6
    assert state.attributes["visibility_unit"] == "km"
    assert state.attributes["precipitation_unit"] == "mm"


async def test_smoke_test_invalid_data(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Smoke test for successfully set-up with default config and check fetcheddata."""
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
    assert state.state == "cloudy"

    assert state.attributes.get("temperature") is None
    assert state.attributes.get("apparent_temperature") is None
    assert state.attributes["temperature_unit"] == "°C"
    assert state.attributes.get("humidity") is None
    assert state.attributes.get("pressure") is None
    assert state.attributes["pressure_unit"] == "hPa"
    assert state.attributes.get("wind_bearing") is None
    assert state.attributes.get("wind_gust_speed") is None
    assert state.attributes.get("wind_speed") is None
    assert state.attributes["wind_speed_unit"] == "km/h"
    assert state.attributes.get("visibility") is None
    assert state.attributes["visibility_unit"] == "km"
    assert state.attributes["precipitation_unit"] == "mm"


async def test_smoke_test_no_forecasts(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Smoke test for successfully set-up with default config and check fetcheddata."""
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
    assert state.state == "cloudy"

    assert state.attributes.get("temperature") is None
    assert state.attributes.get("apparent_temperature") is None
    assert state.attributes["temperature_unit"] == "°C"
    assert state.attributes.get("humidity") is None
    assert state.attributes.get("pressure") is None
    assert state.attributes["pressure_unit"] == "hPa"
    assert state.attributes.get("wind_bearing") is None
    assert state.attributes.get("wind_gust_speed") is None
    assert state.attributes.get("wind_speed") is None
    assert state.attributes["wind_speed_unit"] == "km/h"
    assert state.attributes.get("visibility") is None
    assert state.attributes["visibility_unit"] == "km"
    assert state.attributes["precipitation_unit"] == "mm"
