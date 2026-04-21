"""Tests for the Fumis integration."""

from unittest.mock import MagicMock

from fumis import (
    FumisAuthenticationError,
    FumisConnectionError,
    FumisError,
    FumisStoveOfflineError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_fumis")
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_log"),
    [
        (FumisAuthenticationError, "Authentication with the Fumis online service"),
        (FumisConnectionError, "communicating with the Fumis online service"),
        (FumisStoveOfflineError, "not connected to the internet"),
        (FumisError, "communicating with the Fumis online service"),
    ],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    side_effect: type[Exception],
    expected_log: str,
) -> None:
    """Test the config entry not ready."""
    mock_fumis.update_info.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert expected_log in caplog.text
