"""Test switch platform for Swing2Sleep Smarla integration."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

from pysmarlaapi.connection.exceptions import (
    AuthenticationException,
    ConnectionException,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (AuthenticationException, ConfigEntryState.SETUP_ERROR),
        (ConnectionException, ConfigEntryState.SETUP_RETRY),
    ],
)
@pytest.mark.usefixtures("mock_federwiege")
async def test_init_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    exception: type[Exception],
    expected_state: ConfigEntryState,
) -> None:
    """Test init config setup exception."""
    mock_connection.refresh_token.side_effect = exception

    assert not await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


async def test_init_auth_failure_during_runtime(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege_cls: MagicMock,
) -> None:
    """Test behavior on invalid authentication during runtime."""
    invalid_auth_callback: Callable[[], Awaitable[None]] | None = None

    def mocked_federwiege(_1, _2, callback):
        nonlocal invalid_auth_callback
        invalid_auth_callback = callback
        return mock_federwiege_cls.return_value

    # Mock Federwiege class to gather authentication failure callback
    mock_federwiege_cls.side_effect = mocked_federwiege

    assert await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Check that config entry has no active reauth flows
    assert not any(mock_config_entry.async_get_active_flows(hass, {"reauth"}))

    # Simulate authentication failure during runtime
    assert invalid_auth_callback is not None
    await invalid_auth_callback()
    await hass.async_block_till_done()

    # Check that a reauth flow has been started
    assert any(mock_config_entry.async_get_active_flows(hass, {"reauth"}))
