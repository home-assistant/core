"""Tests for the Concord232 integration setup."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
import requests

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import setup_integration


@pytest.mark.usefixtures("mock_concord232_client")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entry loads both platforms and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("alarm_control_panel.localhost") is not None
    assert hass.states.get("binary_sensor.front_door") is not None

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get("alarm_control_panel.localhost") is None
    assert hass.states.get("binary_sensor.front_door") is None


async def test_platforms_share_one_client(
    hass: HomeAssistant,
    mock_concord232_client_class: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry creates a single client for both platforms."""
    await setup_integration(hass, mock_config_entry)

    assert mock_concord232_client_class.call_count == 1


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(requests.exceptions.ConnectionError("boom"), id="connection"),
        pytest.param(requests.exceptions.Timeout("slow"), id="timeout"),
    ],
)
async def test_setup_connection_error_retries(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    error: requests.exceptions.RequestException,
) -> None:
    """Test an unreachable server defers setup instead of creating entities."""
    mock_concord232_client.list_zones.side_effect = error
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.get("alarm_control_panel.localhost") is None
    assert hass.states.get("binary_sensor.front_door") is None
