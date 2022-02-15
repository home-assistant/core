"""Test Waze Travel Time sensors."""

from unittest.mock import patch

from WazeRouteCalculator import WRCError
import pytest

from homeassistant.components.waze_travel_time.const import DOMAIN

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_update_wrcerror")
def mock_update_wrcerror_fixture():
    """Mock an update to the sensor failed with WRCError."""
    with patch(
        "homeassistant.components.waze_travel_time.sensor.WazeRouteCalculator"
    ) as mock_wrc:
        obj = mock_wrc.return_value
        obj.calc_all_routes_info.side_effect = WRCError("test")
        yield


@pytest.fixture(name="mock_update_keyerror")
def mock_update_keyerror_fixture():
    """Mock an update to the sensor failed with KeyError."""
    with patch(
        "homeassistant.components.waze_travel_time.sensor.WazeRouteCalculator"
    ) as mock_wrc:
        obj = mock_wrc.return_value
        obj.calc_all_routes_info.side_effect = KeyError("test")
        yield


async def test_sensor(hass, mock_update):
    """Test that sensor works."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

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


async def test_sensor_failed_wrcerror(hass, caplog, mock_update_wrcerror):
    """Test that sensor update fails with log message."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.waze_travel_time").state == "unknown"
    assert "Error on retrieving data: " in caplog.text


async def test_sensor_failed_keyerror(hass, caplog, mock_update_keyerror):
    """Test that sensor update fails with log message."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.waze_travel_time").state == "unknown"
    assert "Error retrieving data from server" in caplog.text
