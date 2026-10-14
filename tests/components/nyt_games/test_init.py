"""Tests for the NYT Games integration."""

from unittest.mock import AsyncMock

from nyt_games import NYTGamesAuthenticationError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nyt_games.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_nyt_games_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    for entity in ("wordle", "spelling_bee", "connections"):
        device_entry = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{mock_config_entry.unique_id}_{entity}"),
            mock_config_entry.entry_id,
        )
        assert device_entry is not None
        assert device_entry == snapshot(name=f"device_{entity}")


async def test_setup_auth_failed(
    hass: HomeAssistant,
    mock_nyt_games_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an authentication error during setup starts a reauth flow."""
    mock_nyt_games_client.get_latest_stats.side_effect = NYTGamesAuthenticationError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert (
        mock_config_entry.reason
        == "Authentication with NYT Games failed. Please reauthenticate"
    )
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
