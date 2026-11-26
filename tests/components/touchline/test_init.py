"""Tests for the Touchline integration setup."""

from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytouchline_extended import TouchlineConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import ROOM_STATUS, make_state


@pytest.mark.usefixtures("init_integration")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading and unloading the config entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_on_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchline_controller: MagicMock,
) -> None:
    """Test setup is retried when the controller cannot be reached."""
    mock_touchline_controller.fetch_async.side_effect = TouchlineConnectionError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "field",
    [
        pytest.param("controller_id", id="controller-id"),
        pytest.param("device_id", id="device-id"),
    ],
)
async def test_setup_retry_on_missing_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchline_controller: MagicMock,
    field: str,
) -> None:
    """Test setup is retried when the controller returns no ID for a device."""
    mock_touchline_controller.fetch_async.return_value = make_state(
        replace(ROOM_STATUS, **{field: None})
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
