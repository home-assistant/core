"""Test the Anglian Water integration setup."""

from unittest.mock import AsyncMock, MagicMock

from pyanglianwater.exceptions import InvalidGrantError, TokenRequestError
import pytest

from homeassistant.components.anglian_water.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize("exception", [InvalidGrantError, TokenRequestError])
async def test_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_authenticator: MagicMock,
    mock_anglian_water_client: AsyncMock,
    exception: type[Exception],
) -> None:
    """Test auth errors during setup start reauthentication."""
    mock_anglian_water_authenticator.send_refresh_request.side_effect = exception

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["handler"] == DOMAIN
    assert flow["step_id"] == "reauth_confirm"
    assert flow["context"]["source"] == SOURCE_REAUTH
    assert flow["context"]["entry_id"] == mock_config_entry.entry_id
