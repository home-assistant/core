"""Test the Hypontech Cloud init."""

from unittest.mock import AsyncMock

from hyponcloud import AuthenticationError, RequestError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
        (AuthenticationError, ConfigEntryState.SETUP_ERROR),
        (RequestError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hyponcloud: AsyncMock,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup entry with timeout error."""
    mock_hyponcloud.connect.side_effect = side_effect
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hyponcloud: AsyncMock,
) -> None:
    """Test setup and unload of config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
