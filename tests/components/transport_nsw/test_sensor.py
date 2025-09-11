"""Test the Transport NSW sensor."""

from unittest.mock import patch

from homeassistant.components.transport_nsw.const import CONF_STOP_ID, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_CONFIG_DATA = {
    CONF_API_KEY: "test_api_key",
    CONF_STOP_ID: "test_stop_id",
    CONF_NAME: "Test Stop",
    "route": "",
    "destination": "",
}

MOCK_API_RESPONSE = {
    "route": "Test Route",
    "due": 5,
    "delay": 0,
    "real_time": True,
    "destination": "Test Destination",
    "mode": "Bus",
}


async def test_sensor_setup(hass: HomeAssistant) -> None:
    """Test sensor setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.transport_nsw.coordinator.TransportNSW"
    ) as mock_transport:
        mock_transport_instance = mock_transport.return_value
        mock_transport_instance.get_departures.return_value = MOCK_API_RESPONSE

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_stop")
    assert state is not None
    assert state.state == "5"
    assert state.attributes["stop_id"] == "test_stop_id"
    assert state.attributes["route"] == "Test Route"
    assert state.attributes["delay"] == 0
    assert state.attributes["real_time"] is True
    assert state.attributes["destination"] == "Test Destination"
    assert state.attributes["mode"] == "Bus"


async def test_sensor_with_none_values(hass: HomeAssistant) -> None:
    """Test sensor handles API response with None values correctly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    # Mock API response with None values and n/a values
    mock_response_with_nulls = {
        "route": None,
        "due": "n/a",
        "delay": 0,
        "real_time": True,
        "destination": None,
        "mode": "Bus",
    }

    with patch(
        "homeassistant.components.transport_nsw.coordinator.TransportNSW"
    ) as mock_transport:
        mock_transport_instance = mock_transport.return_value
        mock_transport_instance.get_departures.return_value = mock_response_with_nulls

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_stop")
    assert state is not None
    assert state.state == "unknown"  # "n/a" should become None which becomes "unknown"
    assert state.attributes["stop_id"] == "test_stop_id"
    assert state.attributes["route"] is None  # None values should be preserved
    assert state.attributes["delay"] == 0
    assert state.attributes["real_time"] is True
    assert state.attributes["destination"] is None
    assert state.attributes["mode"] == "Bus"
