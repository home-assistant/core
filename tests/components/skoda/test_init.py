"""Test the Škoda integration setup."""

from unittest.mock import AsyncMock, patch

import pytest
from skoda_public_api.api_layer.exceptions import (
    OpenApiAuthenticationError,
    OpenApiError,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_vehicle: AsyncMock,
) -> None:
    """Test a successful setup and unload of the config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

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
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test errors during the first refresh set the expected entry state."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.skoda.OpenAPIClient.get_vehicle",
        side_effect=exception,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
