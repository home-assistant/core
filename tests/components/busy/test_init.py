"""Test setup and cleanup."""

from unittest.mock import AsyncMock

from busylib.exceptions import BusyBarAPIError, BusyBarRequestError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_unload(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Validate the token before polling and close the client on unload.

    Check the initial request counts and release the client after unload.
    """
    assert init_integration.state is ConfigEntryState.LOADED
    mock_client.access_tokens_list.assert_awaited_once()
    mock_client.status.assert_awaited_once()
    mock_client.wifi_status.assert_awaited_once()
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    mock_client.aclose.assert_awaited_once()


@pytest.mark.parametrize(
    ("method", "error", "state"),
    [
        (
            "access_tokens_list",
            BusyBarAPIError("refused", status_code=401),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            "access_tokens_list",
            BusyBarAPIError("refused", status_code=403),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            "access_tokens_list",
            BusyBarAPIError("server", status_code=500),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            "access_tokens_list",
            BusyBarRequestError("offline"),
            ConfigEntryState.SETUP_RETRY,
        ),
        ("status", BusyBarRequestError("offline"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    method: str,
    error: Exception,
    state: ConfigEntryState,
) -> None:
    """Distinguish permanent token refusal from retryable connection failures.

    Assert the entry state and ensure no reauthentication flow is started.
    """
    getattr(mock_client, method).side_effect = error
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is state
    mock_client.aclose.assert_awaited_once()
    assert not hass.config_entries.flow.async_progress()
