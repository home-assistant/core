"""Test Waze Travel Time sensors."""
import pytest
from pywaze.route_calculator import WRCError

from homeassistant.components.waze_travel_time.const import (
    CONF_AVOID_FERRIES,
    CONF_AVOID_SUBSCRIPTION_ROADS,
    CONF_AVOID_TOLL_ROADS,
    CONF_REALTIME,
    CONF_UNITS,
    CONF_VEHICLE_TYPE,
    DEFAULT_OPTIONS,
    DOMAIN,
    IMPERIAL_UNITS,
)
from homeassistant.core import HomeAssistant

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_config")
async def mock_config_fixture(hass, data, options):
    """Mock a Waze Travel Time config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        options=options,
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture(name="mock_update_wrcerror")
def mock_update_wrcerror_fixture(mock_update):
    """Mock an update to the sensor failed with WRCError."""
    mock_update.side_effect = WRCError("test")
    return mock_update


@pytest.fixture(name="mock_update_keyerror")
def mock_update_keyerror_fixture(mock_update):
    """Mock an update to the sensor failed with KeyError."""
    mock_update.side_effect = KeyError("test")
    return mock_update


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_sensor(hass: HomeAssistant) -> None:
    """Test that sensor works."""
    assert hass.states.get("sensor.waze_travel_time").state == "150"
    assert (
        hass.states.get("sensor.waze_travel_time").attributes["attribution"]
        == "Powered by Waze"
    )
    assert hass.states.get("sensor.waze_travel_time").attributes["duration"] == 150
    assert hass.states.get("sensor.waze_travel_time").attributes["distance"] == 300
    assert hass.states.get("sensor.waze_travel_time").attributes["route"] == "My route"
    assert (
        hass.states.get("sensor.waze_travel_time").attributes["origin"] == "location1"
    )
    assert (
        hass.states.get("sensor.waze_travel_time").attributes["destination"]
        == "location2"
    )
    assert (
        hass.states.get("sensor.waze_travel_time").attributes["unit_of_measurement"]
        == "min"
    )
    assert hass.states.get("sensor.waze_travel_time").attributes["icon"] == "mdi:car"


@pytest.mark.parametrize(
    ("data", "options"),
    [
        (
            MOCK_CONFIG,
            {
                CONF_UNITS: IMPERIAL_UNITS,
                CONF_REALTIME: True,
                CONF_VEHICLE_TYPE: "car",
                CONF_AVOID_TOLL_ROADS: True,
                CONF_AVOID_SUBSCRIPTION_ROADS: True,
                CONF_AVOID_FERRIES: True,
            },
        )
    ],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_imperial(hass: HomeAssistant) -> None:
    """Test that the imperial option works."""
    assert hass.states.get("sensor.waze_travel_time").attributes[
        "distance"
    ] == pytest.approx(186.4113)


@pytest.mark.usefixtures("mock_update_wrcerror")
async def test_sensor_failed_wrcerror(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that sensor update fails with log message."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, options=DEFAULT_OPTIONS, entry_id="test"
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.waze_travel_time").state == "unknown"
    assert "Error on retrieving data: " in caplog.text


@pytest.mark.usefixtures("mock_update_keyerror")
async def test_sensor_failed_keyerror(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that sensor update fails with log message."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, options=DEFAULT_OPTIONS, entry_id="test"
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.waze_travel_time").state == "unknown"
    assert "Error retrieving data from server" in caplog.text
