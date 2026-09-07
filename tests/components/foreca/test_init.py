"""Test the Foreca integration setup."""

from unittest.mock import AsyncMock, MagicMock

from pyforeca import ForecaAuthError, ForecaConnectionError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_foreca_client")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading and unloading the config entry."""
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_on_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test the entry is retried when the API is unreachable."""
    mock_foreca_client.current.side_effect = ForecaConnectionError
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_fails_auth_on_rejected_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test a rejected API key puts the entry into an auth-failed state."""
    mock_foreca_client.current.side_effect = ForecaAuthError
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    # Raising ConfigEntryAuthFailed starts a reauth flow, so the flow has to
    # have the step: without it the started flow raises in the background.
    flows = hass.config_entries.flow.async_progress()
    assert [flow["step_id"] for flow in flows] == ["reauth_confirm"]


async def test_documented_request_budget(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test one update costs the three requests the documentation promises.

    The docs page quotes this number against the Freemium daily limit, so a new
    call added to the coordinator has to be a deliberate change here too.
    """
    await init_integration(hass, mock_config_entry)

    awaited = {
        name: attr.await_count
        for name in dir(mock_foreca_client)
        if not name.startswith("_")
        and isinstance(attr := getattr(mock_foreca_client, name), AsyncMock)
        and attr.await_count
    }
    assert awaited == {"current": 1, "forecast_daily": 1, "forecast_hourly": 1}
    assert sum(awaited.values()) == 3
