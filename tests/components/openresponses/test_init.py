"""Tests for the Open Responses integration setup."""

from unittest.mock import MagicMock

from openresponses_client import (
    APIConnectionError,
    AuthenticationError,
    NotFoundError,
    Response,
    UnprocessableEntityError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test loading and unloading the integration."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        pytest.param(
            UnprocessableEntityError("Missing model", status=422),
            ConfigEntryState.LOADED,
            id="empty_request_rejected",
        ),
        pytest.param(
            [Response()],
            ConfigEntryState.LOADED,
            id="empty_request_accepted",
        ),
        pytest.param(
            AuthenticationError("Invalid key", status=401),
            ConfigEntryState.SETUP_ERROR,
            id="invalid_auth",
        ),
        pytest.param(
            APIConnectionError("Connection refused"),
            ConfigEntryState.SETUP_RETRY,
            id="cannot_connect",
        ),
        pytest.param(
            NotFoundError("Not found", status=404),
            ConfigEntryState.SETUP_RETRY,
            id="not_found",
        ),
    ],
)
async def test_setup_connection_check(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    side_effect: Exception | list[Response],
    expected_state: ConfigEntryState,
) -> None:
    """Test the connection check during setup."""
    mock_client.create.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
