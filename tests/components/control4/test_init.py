"""Test the Control4 integration setup."""

from unittest.mock import MagicMock

from pyControl4.error_handling import BadCredentials

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_bad_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_account: MagicMock,
) -> None:
    """Test setup fails with invalid credentials."""
    mock_c4_account.get_account_bearer_token.side_effect = BadCredentials(
        "Invalid credentials"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == (
        "Error authenticating with the Control4 account API, incorrect username or"
        " password"
    )
