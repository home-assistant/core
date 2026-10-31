"""Test the Compensation integration setup."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.compensation.const import (
    CONF_COMPENSATED_VALUE,
    CONF_UNCOMPENSATED_VALUE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

ENTITY_ID = "sensor.my_compensation"


async def test_setup_and_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up and unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    hass.states.async_set("sensor.uncompensated", "5")
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "6.0"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "data_points",
    [
        [
            {CONF_UNCOMPENSATED_VALUE: 0.0, CONF_COMPENSATED_VALUE: 1.0},
            {CONF_UNCOMPENSATED_VALUE: 0.0, CONF_COMPENSATED_VALUE: 1.0},
        ]
    ],
)
async def test_setup_entry_polyfit_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup fails when no polynomial can be fitted to the data points."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "setup_error"
    assert hass.states.get(ENTITY_ID) is None


async def test_source_entity_new_entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the config entry follows a renamed source entity."""
    source_entry = entity_registry.async_get_or_create(
        "sensor", "test", "unique", suggested_object_id="uncompensated"
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry.async_update_entity(
        source_entry.entity_id, new_entity_id="sensor.new_entity_id"
    )
    await hass.async_block_till_done()

    assert mock_config_entry.options[CONF_ENTITY_ID] == "sensor.new_entity_id"
    assert mock_config_entry.state is ConfigEntryState.LOADED

    hass.states.async_set("sensor.new_entity_id", "5")
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "6.0"
