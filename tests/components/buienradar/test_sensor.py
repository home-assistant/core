"""The tests for the Buienradar sensor platform."""

from http import HTTPStatus

from homeassistant.components.buienradar.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, load_fixture, load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

CONDITIONS = [
    "barometerfc",
    "barometerfcname",
    "condition",
    "conditioncode",
    "feeltemperature",
    "groundtemperature",
    "windspeed",
    "windforce",
    "winddirection",
    "windazimuth",
    "pressure",
    "visibility",
    "windgust",
    "precipitation",
    "precipitation_forecast_average",
    "precipitation_forecast_total",
    "rainlast24hour",
    "rainlasthour",
    "irradiance",
    "temperature_1d",
    "temperature_2d",
    "temperature_3d",
    "temperature_4d",
    "temperature_5d",
    "mintemp_1d",
    "mintemp_2d",
    "mintemp_3d",
    "mintemp_4d",
    "mintemp_5d",
    "rain_1d",
    "rain_2d",
    "rain_3d",
    "rain_4d",
    "rain_5d",
    "minrain_1d",
    "minrain_2d",
    "minrain_3d",
    "minrain_4d",
    "minrain_5d",
    "maxrain_1d",
    "maxrain_2d",
    "maxrain_3d",
    "maxrain_4d",
    "maxrain_5d",
    "rainchance_1d",
    "rainchance_2d",
    "rainchance_3d",
    "rainchance_4d",
    "rainchance_5d",
    "sunchance_1d",
    "sunchance_2d",
    "sunchance_3d",
    "sunchance_4d",
    "sunchance_5d",
    "windforce_1d",
    "windforce_2d",
    "windforce_3d",
    "windforce_4d",
    "windforce_5d",
    "windspeed_1d",
    "windspeed_2d",
    "windspeed_3d",
    "windspeed_4d",
    "windspeed_5d",
    "windazimuth_1d",
    "windazimuth_2d",
    "windazimuth_3d",
    "windazimuth_4d",
    "windazimuth_5d",
    "condition_1d",
    "condition_2d",
    "condition_3d",
    "condition_4d",
    "condition_5d",
    "humidity",
    "stationname",
    "temperature",
]
TEST_CFG_DATA = {CONF_LATITUDE: 51.5288504, CONF_LONGITUDE: 5.4002156}


async def test_smoke_test_setup_component(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Smoke test for successfully set-up with default config."""
    aioclient_mock.get(
        "https://data.buienradar.nl/2.0/feed/json", status=HTTPStatus.NOT_FOUND
    )
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA)

    mock_entry.add_to_hass(hass)

    for cond in CONDITIONS:
        entity_registry.async_get_or_create(
            domain="sensor",
            platform="buienradar",
            unique_id=f"{TEST_CFG_DATA[CONF_LATITUDE]:2.6f}{TEST_CFG_DATA[CONF_LONGITUDE]:2.6f}{cond}",
            config_entry=mock_entry,
            original_name=f"Buienradar {cond}",
        )
    await hass.async_block_till_done()

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    for cond in CONDITIONS:
        state = hass.states.get(f"sensor.buienradar_51_5288505_400216{cond}")
        assert state.state == "unknown"


async def test_smoke_test_data(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Smoke test for successfully set-up with default configand data."""
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

    for cond in CONDITIONS:
        entity_registry.async_get_or_create(
            domain="sensor",
            platform="buienradar",
            unique_id=f"{TEST_CFG_DATA[CONF_LATITUDE]:2.6f}{TEST_CFG_DATA[CONF_LONGITUDE]:2.6f}{cond}",
            config_entry=mock_entry,
            original_name=f"Buienradar {cond}",
        )
    await hass.async_block_till_done()

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    expected = {
        "barometerfc": "5",
        "barometerfcname": "Unstable",
        "condition": "cloudy",
        "conditioncode": "c",
        "feeltemperature": "20.5",
        "groundtemperature": "19.8",
        "windspeed": "14.4",
        "windforce": "3",
        "winddirection": "NO",
        "windazimuth": "38",
        "humidity": "76",
        "pressure": "1020.0",
        "visibility": "32.6",
        "windgust": "23.4",
        "precipitation": "0.0",
        "precipitation_forecast_average": "0.0",
        "precipitation_forecast_total": "0.0",
        "rainlast24hour": "2.2",
        "rainlasthour": "0.0",
        "temperature_1d": "23.5",
        "temperature_2d": "26.5",
        "temperature_3d": "25.5",
        "temperature_4d": "24.5",
        "temperature_5d": "23.5",
        "mintemp_1d": "15.0",
        "mintemp_2d": "17.0",
        "mintemp_3d": "18.0",
        "mintemp_4d": "17.0",
        "mintemp_5d": "14.0",
        "rain_1d": "4.0",
        "rain_2d": "3.0",
        "rain_3d": "3.5",
        "rain_4d": "1.5",
        "rain_5d": "1.0",
        "minrain_1d": "0.0",
        "minrain_2d": "0.0",
        "minrain_3d": "1.0",
        "minrain_4d": "0.0",
        "minrain_5d": "0.0",
        "maxrain_1d": "8.0",
        "maxrain_2d": "6.0",
        "maxrain_3d": "6.0",
        "maxrain_4d": "3.0",
        "maxrain_5d": "2.0",
        "rainchance_1d": "30",
        "rainchance_2d": "30",
        "rainchance_3d": "60",
        "rainchance_4d": "40",
        "rainchance_5d": "40",
        "sunchance_1d": "50",
        "sunchance_2d": "60",
        "sunchance_3d": "20",
        "sunchance_4d": "30",
        "sunchance_5d": "30",
        "windforce_1d": "4",
        "windforce_2d": "3",
        "windforce_3d": "2",
        "windforce_4d": "3",
        "windforce_5d": "2",
        "windspeed_1d": "20.4",
        "windspeed_2d": "13.0",
        "windspeed_3d": "7.4",
        "windspeed_4d": "13.0",
        "windspeed_5d": "7.4",
        "windazimuth_1d": "45",
        "windazimuth_2d": "90",
        "windazimuth_3d": "225",
        "windazimuth_4d": "270",
        "windazimuth_5d": "180",
        "condition_1d": "cloudy",
        "condition_2d": "cloudy",
        "condition_3d": "rainy",
        "condition_4d": "rainy",
        "condition_5d": "rainy",
        "irradiance": "526",
        "stationname": "Eindhoven (6370)",
        "temperature": "20.4",
    }
    for cond in CONDITIONS:
        state = hass.states.get(f"sensor.buienradar_51_5288505_400216{cond}")
        assert state.state == expected[cond]
