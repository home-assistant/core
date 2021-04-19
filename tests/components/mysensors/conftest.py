"""Provide common mysensors fixtures."""
import pytest

from homeassistant.config_entries import ENTRY_STATE_LOADED

from tests.common import MockConfigEntry


@pytest.fixture(name="mqtt")
async def mock_mqtt_fixture(hass):
    """Mock the MQTT integration."""
    mqtt_entry = MockConfigEntry(domain="mqtt", state=ENTRY_STATE_LOADED)
    mqtt_entry.add_to_hass(hass)
    return mqtt_entry
