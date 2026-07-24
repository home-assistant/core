"""Test the initialization of Yardian."""

from unittest.mock import AsyncMock

import pytest
from pyyardian import NetworkException, NotAuthorizedException

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("exception", "entry_state"),
    [
        (NotAuthorizedException, ConfigEntryState.SETUP_ERROR),
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
        (NetworkException, ConfigEntryState.SETUP_RETRY),
        (Exception, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_unauthorized(
    hass: HomeAssistant,
    mock_yardian_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    entry_state: ConfigEntryState,
) -> None:
    """Test setup when unauthorized."""
    mock_yardian_client.fetch_device_state.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is entry_state
