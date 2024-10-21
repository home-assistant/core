"""The tests for the Buienradar sensor platform."""

from http import HTTPStatus

from syrupy.assertion import SnapshotAssertion

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


async def test_sensor_values(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for fetching (mocked) weather data and checking sensor values."""
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

    # Explicitly call async_get_or_create to make sure all sensors in the test have been / are created.
    # BrSensor sets '_attr_entity_registry_enabled_default=false', so no sensor will get added into
    # the registry on platform creation.
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
        assert state == snapshot
