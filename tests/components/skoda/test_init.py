"""Test the Škoda integration setup."""

from unittest.mock import AsyncMock, patch

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


async def test_setup_auth_failure_sets_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an authentication failure during setup marks the entry as failed."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.skoda.OpenAPIClient.get_vehicle",
        side_effect=OpenApiAuthenticationError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_update_failed_starts_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a generic API error during first refresh triggers a setup retry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.skoda.OpenAPIClient.get_vehicle",
        side_effect=OpenApiError("boom"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_unexpected_error_starts_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a wholly unexpected exception during first refresh triggers a setup retry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.skoda.OpenAPIClient.get_vehicle",
        side_effect=RuntimeError("boom"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
