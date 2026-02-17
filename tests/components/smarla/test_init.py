"""Test switch platform for Swing2Sleep Smarla integration."""

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
    mock_refresh_token: MagicMock,
    exception: type[Exception],
    expected_state: ConfigEntryState,
) -> None:
    """Test init config setup exception."""
    mock_refresh_token.side_effect = exception

    assert not await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


async def test_init_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege_cls: MagicMock,
) -> None:
    """Test behavior on invalid authentication during runtime."""
    assert await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not any(mock_config_entry.async_get_active_flows(hass, {"reauth"}))

    auth_failed_cb = mock_federwiege_cls.call_args.args[2]
    await auth_failed_cb()
    await hass.async_block_till_done()
    assert any(mock_config_entry.async_get_active_flows(hass, {"reauth"}))
