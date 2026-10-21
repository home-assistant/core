"""Tests for the NYT Games diagnostics."""

from unittest.mock import AsyncMock

from nyt_games import WordleStats
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_load_fixture
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nyt_games.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.mark.usefixtures("mock_nyt_games_client")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await setup_integration(hass, mock_config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


async def test_diagnostics_new_account(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_nyt_games_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for an account without game statistics."""
    mock_nyt_games_client.get_latest_stats.return_value = WordleStats.from_json(
        await async_load_fixture(hass, "new_account.json", DOMAIN)
    ).player.stats
    mock_nyt_games_client.get_connections.return_value = None
    await setup_integration(hass, mock_config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
