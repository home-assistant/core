"""Test switch platform for Swing2Sleep Smarla integration."""

from unittest.mock import MagicMock

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_federwiege")
async def test_init_invalid_auth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_connection: MagicMock
) -> None:
    """Test init invalid authentication behavior."""
    mock_connection.refresh_token.return_value = False

    assert not await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
