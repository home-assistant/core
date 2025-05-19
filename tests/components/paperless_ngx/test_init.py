"""Test the Paperless-ngx integration initialization."""

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
        (InitializationError(), ConfigEntryState.SETUP_ERROR, "cannot_connect"),
        (Exception("BOOM!"), ConfigEntryState.SETUP_ERROR, "unknown"),
    ],
)
async def test_setup_config_error_handling(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
    side_effect,
    expected_state,
    expected_error_key,
) -> None:
    """Test all initialization error paths during setup."""
    mock_client.initialize.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state == expected_state
    assert mock_config_entry.error_reason_translation_key == expected_error_key
