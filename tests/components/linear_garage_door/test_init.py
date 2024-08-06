"""Test Linear Garage Door init."""

from unittest.mock import AsyncMock

from linear_garage_door import InvalidLoginError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_unload_entry(
    hass: HomeAssistant, mock_linear: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the unload entry."""

    await setup_integration(hass, mock_config_entry, [])
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "entry_state"),
    [
        (
            InvalidLoginError(
                "Login provided is invalid, please check the email and password"
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (InvalidLoginError("Invalid login"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_linear: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    entry_state: ConfigEntryState,
) -> None:
    """Test reauth trigger setup."""

    mock_linear.login.side_effect = side_effect

    await setup_integration(hass, mock_config_entry, [])
    assert mock_config_entry.state == entry_state
