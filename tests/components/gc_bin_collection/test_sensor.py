"""Tests for the Gold Coast Bin Collection sensor platform."""

from unittest.mock import MagicMock

import requests

from homeassistant.components.gc_bin_collection.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_BIN_DATA, MOCK_PROPERTY_ID

from tests.common import MockConfigEntry


async def test_sensors_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gcbinspy: MagicMock,
) -> None:
    """Test that all three sensors are created with correct state."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_reg = er.async_get(hass)

    for key, expected_date in (
        ("landfill", MOCK_BIN_DATA["landfill"]),
        ("recycling", MOCK_BIN_DATA["recycling"]),
        ("organics", MOCK_BIN_DATA["organics"]),
    ):
        entity_id = entity_reg.async_get_entity_id(
            "sensor", DOMAIN, f"{MOCK_PROPERTY_ID}_{key}"
        )
        assert entity_id is not None, f"Sensor '{key}' not registered"
        state = hass.states.get(entity_id)
        assert state is not None, f"State for '{key}' not found"
        assert state.state == expected_date.isoformat(), (
            f"Unexpected state for '{key}': {state.state}"
        )


async def test_sensor_unique_ids(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gcbinspy: MagicMock,
) -> None:
    """Test that sensors have correct unique IDs."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_reg = er.async_get(hass)

    for key in ("landfill", "recycling", "organics"):
        entity_id = entity_reg.async_get_entity_id(
            "sensor", DOMAIN, f"{MOCK_PROPERTY_ID}_{key}"
        )
        assert entity_id is not None, f"Unique ID for sensor '{key}' not found"


async def test_sensor_unavailable_on_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gcbinspy: MagicMock,
) -> None:
    """Test that setup fails (retry) when API raises an error."""
    mock_gcbinspy.update_next_bin_days.side_effect = (
        requests.exceptions.ConnectionError("API down")
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state.name in ("SETUP_RETRY", "SETUP_ERROR", "NOT_LOADED")


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gcbinspy: MagicMock,
) -> None:
    """Test that unloading a config entry works correctly."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_reg = er.async_get(hass)
    landfill_entity_id = entity_reg.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_PROPERTY_ID}_landfill"
    )
    assert landfill_entity_id is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(landfill_entity_id)
    assert state is None or state.state == "unavailable"
