"""Test the Transport NSW sensor."""

from unittest.mock import patch

import pytest

from homeassistant.components.transport_nsw.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_CONFIG_DATA = {
    CONF_API_KEY: "test_api_key",
    "stop_id": "test_stop_id",
    CONF_NAME: "Test Stop",
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
        "homeassistant.components.transport_nsw.sensor.TransportNSW.get_departures",
        return_value=MOCK_API_RESPONSE,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_stop")
    assert state is not None
    assert state.state == "5"
    assert state.attributes["stop_id"] == "test_stop_id"
    assert state.attributes["route"] == "Test Route"
    assert state.attributes["destination"] == "Test Destination"
    assert state.attributes["mode"] == "Bus"


async def test_sensor_unavailable_api(hass: HomeAssistant) -> None:
    """Test sensor when API is unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.transport_nsw.sensor.TransportNSW.get_departures",
        side_effect=Exception("API Error"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_stop")
    assert state is not None
    assert state.state == "unavailable"
