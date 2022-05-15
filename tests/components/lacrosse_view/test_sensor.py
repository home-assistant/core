"""Test the LaCrosse View sensors."""
from unittest.mock import patch

from homeassistant.components.lacrosse_view import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import MOCK_ENTRY_DATA, TEST_NO_PERMISSION_SENSOR, TEST_SENSOR

from tests.common import MockConfigEntry


async def test_entities_added(hass: HomeAssistant) -> None:
    """Test the entities are added."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    with patch("lacrosse_view.LaCrosse.login", return_value=True), patch(
        "lacrosse_view.LaCrosse.get_sensors", return_value=[TEST_SENSOR]
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DOMAIN]
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state == ConfigEntryState.LOADED
    assert hass.states.get("sensor.test_test_temperature")


async def test_sensor_permission(hass: HomeAssistant, caplog) -> None:
    """Test if it raises a warning when there is no permission to read the sensor."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    with patch("lacrosse_view.LaCrosse.login", return_value=True), patch(
        "lacrosse_view.LaCrosse.get_sensors", return_value=[TEST_NO_PERMISSION_SENSOR]
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DOMAIN]
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state == ConfigEntryState.LOADED
    assert hass.states.get("sensor.test_test_temperature") is None
    assert "No permission to read sensor" in caplog.text
