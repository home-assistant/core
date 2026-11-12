"""Tests for the Papouch initialization and coordinator."""

from unittest.mock import patch

from aiopapouch.exceptions import (
    DeviceAuthError,
    DeviceConnectionError,
    DeviceParseError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_unload_and_reload(
    hass: HomeAssistant, mock_config_entry, mock_papouch_client
) -> None:
    """Test successful setup, reload and unload of the integration."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (DeviceAuthError(), ConfigEntryState.SETUP_ERROR),
        (DeviceParseError(), ConfigEntryState.SETUP_RETRY),
        (DeviceConnectionError(), ConfigEntryState.SETUP_RETRY),
        (
            None,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry,
    mock_papouch_client,
    side_effect,
    expected_state,
) -> None:
    """Test setup handles different errors and unknown device correctly."""
    _, mock_create, _ = mock_papouch_client

    if side_effect is None:
        mock_create.return_value = None
    else:
        mock_create.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (DeviceAuthError(), ConfigEntryState.SETUP_ERROR),
        (DeviceConnectionError(), ConfigEntryState.SETUP_RETRY),
        (DeviceParseError(), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_coordinator_errors(
    hass: HomeAssistant,
    mock_config_entry,
    mock_papouch_client,
    side_effect,
    expected_state,
) -> None:
    """Test coordinator handles different errors during update correctly."""
    _, _, mock_device = mock_papouch_client
    mock_device.get_fresh_data.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (DeviceConnectionError(), ConfigEntryState.SETUP_RETRY),
        (DeviceAuthError(), ConfigEntryState.SETUP_ERROR),
        (DeviceParseError(), ConfigEntryState.SETUP_RETRY),
    ],
)
@patch("homeassistant.components.papouch.PapouchHTTPClient.get_device_info")
async def test_setup_device_info_errors(
    mock_get_device_info,
    mock_config_entry,
    hass: HomeAssistant,
    side_effect,
    expected_state,
) -> None:
    """Test setup handles different get_device_info errors correctly."""

    mock_get_device_info.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
