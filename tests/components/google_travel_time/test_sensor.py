"""Test the Google Maps Travel Time sensors."""

from unittest.mock import patch

import pytest

from homeassistant.components.google_travel_time.const import (
    CONF_ARRIVAL_TIME,
    CONF_DEPARTURE_TIME,
    CONF_TRAVEL_MODE,
    DOMAIN,
)

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_update")
def mock_update_fixture():
    """Mock an update to the sensor."""
    with patch("homeassistant.components.google_travel_time.sensor.Client"), patch(
        "homeassistant.components.google_travel_time.sensor.distance_matrix"
    ) as distance_matrix_mock:
        distance_matrix_mock.return_value = {
            "rows": [
                {
                    "elements": [
                        {
                            "duration_in_traffic": {
                                "value": 1620,
                                "text": "27 mins",
                            },
                            "duration": {
                                "value": 1560,
                                "text": "26 mins",
                            },
                            "distance": {"text": "21.3 km"},
                        }
                    ]
                }
            ]
        }
        yield distance_matrix_mock


@pytest.fixture(name="mock_update_duration")
def mock_update_duration_fixture(mock_update):
    """Mock an update to the sensor returning no duration_in_traffic."""
    mock_update.return_value = {
        "rows": [
            {
                "elements": [
                    {
                        "duration": {
                            "value": 1560,
                            "text": "26 mins",
                        },
                        "distance": {"text": "21.3 km"},
                    }
                ]
            }
        ]
    }
    yield mock_update


@pytest.fixture(name="mock_update_empty")
def mock_update_empty_fixture(mock_update):
    """Mock an update to the sensor with an empty response."""
    mock_update.return_value = None
    yield mock_update


@pytest.mark.usefixtures("mock_update")
async def test_sensor(hass):
    """Test that sensor works."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.google_travel_time").state == "27"
    assert (
        hass.states.get("sensor.google_travel_time").attributes["attribution"]
        == "Powered by Google"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["duration"] == "26 mins"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["duration_in_traffic"]
        == "27 mins"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["distance"] == "21.3 km"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["origin"] == "location1"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["destination"]
        == "location2"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["unit_of_measurement"]
        == "min"
    )


@pytest.mark.usefixtures("mock_update_duration")
async def test_sensor_duration(hass):
    """Test that sensor works with no duration_in_traffic in response."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.google_travel_time").state == "26"


@pytest.mark.usefixtures("mock_update_empty")
async def test_sensor_empty_response(hass):
    """Test that sensor works for an empty response."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.google_travel_time").state == "unknown"


@pytest.mark.usefixtures("mock_update")
async def test_sensor_departure_time(hass):
    """Test that sensor works for departure time."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        options={
            CONF_DEPARTURE_TIME: "10:00",
        },
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.google_travel_time").state == "27"


@pytest.mark.usefixtures("mock_update")
async def test_sensor_departure_time_custom_timestamp(hass):
    """Test that sensor works for departure time with a custom timestamp."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        options={
            CONF_DEPARTURE_TIME: "test",
        },
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.google_travel_time").state == "27"


@pytest.mark.usefixtures("mock_update")
async def test_sensor_arrival_time(hass):
    """Test that sensor works for arrival time."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        options={
            CONF_ARRIVAL_TIME: "10:00",
        },
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.google_travel_time").state == "27"


@pytest.mark.usefixtures("mock_update")
async def test_sensor_arrival_time_custom_timestamp(hass):
    """Test that sensor works for arrival time with a custom timestamp."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        options={
            CONF_ARRIVAL_TIME: "custom_timestamp",
        },
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.google_travel_time").state == "27"


@pytest.mark.usefixtures("mock_update")
async def test_sensor_deprecation_warning(hass, caplog):
    """Test that sensor setup prints a deprecating warning for old configs."""
    data = MOCK_CONFIG.copy()
    data[CONF_TRAVEL_MODE] = "driving"
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.google_travel_time").state == "27"
    wstr = (
        "Google Travel Time: travel_mode is deprecated, please "
        "add mode to the options dictionary instead!"
    )
    assert wstr in caplog.text
