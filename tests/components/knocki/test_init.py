"""Test the Home Knocki init module."""

from unittest.mock import AsyncMock

from knocki import KnockiConnectionError, KnockiInvalidAuthError
import pytest

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_knocki_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        pytest.param(
            KnockiConnectionError, ConfigEntryState.SETUP_RETRY, id="connection"
        ),
        pytest.param(KnockiInvalidAuthError, ConfigEntryState.SETUP_ERROR, id="auth"),
    ],
)
async def test_initialization_failure(
    hass: HomeAssistant,
    mock_knocki_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test initialization failure."""
    mock_knocki_client.get_triggers.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state


async def test_initialization_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_knocki_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an invalid token starts a reauthentication flow."""
    mock_knocki_client.get_triggers.side_effect = KnockiInvalidAuthError

    await setup_integration(hass, mock_config_entry)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
