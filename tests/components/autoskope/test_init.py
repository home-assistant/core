"""Test Autoskope integration setup."""

from unittest.mock import AsyncMock

from autoskope_client.models import CannotConnect, InvalidAuth
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_client: AsyncMock,
) -> None:
    """Test successful setup and unload of entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (InvalidAuth("Invalid credentials"), ConfigEntryState.SETUP_ERROR),
        (CannotConnect("Connection failed"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_client: AsyncMock,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup with authentication and connection errors."""
    mock_autoskope_client.connect.side_effect = exception

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is expected_state
