"""Tests for the MELCloud integration setup."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

from aiohttp import ClientConnectionError, ClientResponseError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        pytest.param(TimeoutError, ConfigEntryState.SETUP_RETRY, id="timeout"),
        pytest.param(
            ClientConnectionError, ConfigEntryState.SETUP_RETRY, id="connection_error"
        ),
        pytest.param(
            ClientResponseError(MagicMock(), (), status=HTTPStatus.TOO_MANY_REQUESTS),
            ConfigEntryState.SETUP_RETRY,
            id="rate_limited",
        ),
        pytest.param(
            ClientResponseError(
                MagicMock(), (), status=HTTPStatus.INTERNAL_SERVER_ERROR
            ),
            ConfigEntryState.SETUP_RETRY,
            id="server_error",
        ),
        pytest.param(
            ClientResponseError(MagicMock(), (), status=HTTPStatus.UNAUTHORIZED),
            ConfigEntryState.SETUP_ERROR,
            id="unauthorized",
        ),
    ],
)
async def test_setup_entry_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test communication errors during setup are retried."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.melcloud.get_devices", side_effect=side_effect
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
