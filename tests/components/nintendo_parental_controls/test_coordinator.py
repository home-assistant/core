"""Test coordinator error handling."""

from unittest.mock import AsyncMock

from pynintendoauth.exceptions import (
    HttpException,
    InvalidOAuthConfigurationException,
    InvalidSessionTokenException,
)
from pynintendoparental.exceptions import NoDevicesFoundException
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("exception", "translation_key", "expected_state", "expected_log_message"),
    [
        (
            InvalidOAuthConfigurationException(
                status_code=401, message="Authentication failed"
            ),
            "invalid_auth",
            ConfigEntryState.SETUP_ERROR,
            None,
        ),
        (
            NoDevicesFoundException(),
            "no_devices_found",
            ConfigEntryState.SETUP_ERROR,
            None,
        ),
        (
            HttpException(
                status_code=400, error_code="update_required", message="Update required"
            ),
            "update_required",
            ConfigEntryState.SETUP_ERROR,
            None,
        ),
        (
            HttpException(
                status_code=500, error_code="unknown", message="Unknown error"
            ),
            None,
            ConfigEntryState.SETUP_RETRY,
            None,
        ),
        (
            InvalidSessionTokenException(
                status_code=403, error_code="invalid_token", message="Invalid token"
            ),
            None,
            ConfigEntryState.SETUP_RETRY,
            "Session token invalid, will renew on next update",
        ),
    ],
)
async def test_update_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    exception: Exception,
    translation_key: str,
    expected_state: ConfigEntryState,
    expected_log_message: str | None,
) -> None:
    """Test handling of update errors."""
    mock_nintendo_client.update.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    # Ensure no entities are created
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 0

    # Ensure the config entry is marked as expected state
    assert mock_config_entry.state is expected_state

    # Ensure the correct translation key is used in the error
    assert mock_config_entry.error_reason_translation_key == translation_key

    # If there's an expected log message, check that it was logged
    if expected_log_message:
        assert expected_log_message in caplog.text
