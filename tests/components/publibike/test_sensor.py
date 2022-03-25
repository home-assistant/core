"""Tests for PubliBike sensors."""
from unittest.mock import patch

from homeassistant.components.publibike.const import (
    BATTERY_LIMIT,
    DOMAIN,
    LATITUDE,
    LONGITUDE,
    STATION_ID,
)

from tests.common import MockConfigEntry
from tests.components.publibike.mocks import _get_mock_bike


async def _assert_states(hass):
    state = hass.states.get("sensor.test_station_e_bikes")
    assert state.state == "1"
    expected_attributes = {
        "All E-bikes": 2,
        "friendly_name": "test_station - E-bikes",
    }
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value
    state = hass.states.get("sensor.test_station_bikes")
    assert state.state == "2"
    expected_attributes = {
        "friendly_name": "test_station - Bikes",
    }
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value


async def test_sensors_with_station_id(hass):
    """Test creation of the sensors given station ID."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            STATION_ID: 123,
            BATTERY_LIMIT: 99,
        },
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.publibike.config_flow.PubliBike",
        return_value=_get_mock_bike(),
    ), patch(
        "homeassistant.components.publibike.PubliBike", return_value=_get_mock_bike()
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await _assert_states(hass)


async def test_sensors_with_location(hass):
    """Test creation of the sensors given coordinates."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            BATTERY_LIMIT: 99,
            LATITUDE: 1.0,
            LONGITUDE: 2.0,
        },
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.publibike.config_flow.PubliBike",
        return_value=_get_mock_bike(),
    ), patch(
        "homeassistant.components.publibike.PubliBike", return_value=_get_mock_bike()
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await _assert_states(hass)


async def test_sensors_without_location(hass):
    """Test creation of the sensors using default coordinates."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            BATTERY_LIMIT: 99,
        },
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.publibike.config_flow.PubliBike",
        return_value=_get_mock_bike(),
    ), patch(
        "homeassistant.components.publibike.PubliBike", return_value=_get_mock_bike()
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await _assert_states(hass)
