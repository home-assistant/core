"""Test the Compensation integration setup."""

import pytest

from homeassistant.components.compensation.const import (
    CONF_COMPENSATED_VALUE,
    CONF_UNCOMPENSATED_VALUE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

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
