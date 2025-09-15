"""Test the Paperless-ngx integration initialization."""

from unittest.mock import AsyncMock

from pypaperless.exceptions import (
    InitializationError,
    PaperlessConnectionError,
    PaperlessForbiddenError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_load_config_status_forbidden(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_paperless: AsyncMock,
) -> None:
    """Test loading and unloading the integration."""
    mock_paperless.status.side_effect = PaperlessForbiddenError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_state", "expected_error_key"),
    [
        (PaperlessConnectionError(), ConfigEntryState.SETUP_RETRY, "cannot_connect"),
        (PaperlessInvalidTokenError(), ConfigEntryState.SETUP_ERROR, "invalid_api_key"),
        (
            PaperlessInactiveOrDeletedError(),
            ConfigEntryState.SETUP_ERROR,
            "user_inactive_or_deleted",
        ),
        (PaperlessForbiddenError(), ConfigEntryState.SETUP_ERROR, "forbidden"),
        (InitializationError(), ConfigEntryState.SETUP_RETRY, "cannot_connect"),
    ],
)
async def test_setup_config_error_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_paperless: AsyncMock,
    side_effect: Exception,
    expected_state: ConfigEntryState,
    expected_error_key: str,
) -> None:
    """Test all initialization error paths during setup."""
    mock_paperless.initialize.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state == expected_state
    assert mock_config_entry.error_reason_translation_key == expected_error_key
