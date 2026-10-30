"""Test the Škoda integration setup."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from skoda_public_api.api_layer.exceptions import (
    OpenApiAuthenticationError,
    OpenApiError,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
) -> None:
    """Test a successful setup and unload of the config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        pytest.param(
            OpenApiAuthenticationError(),
            ConfigEntryState.SETUP_ERROR,
            id="auth_failure",
        ),
        pytest.param(
            OpenApiError("boom"), ConfigEntryState.SETUP_RETRY, id="api_error"
        ),
        pytest.param(
            RuntimeError("boom"), ConfigEntryState.SETUP_RETRY, id="unexpected_error"
        ),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test errors during the first refresh set the expected entry state."""
    mock_skoda_client.get_vehicle.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state
