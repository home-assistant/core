"""Tests for the NYT Games sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from nyt_games import NYTGamesError, WordleStats
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.nyt_games.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_fixture,
    snapshot_platform,
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_nyt_games_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_updating_exception(
    hass: HomeAssistant,
    mock_nyt_games_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test handling an exception during update."""
    await setup_integration(hass, mock_config_entry)

    mock_nyt_games_client.get_latest_stats.side_effect = NYTGamesError

    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wordle_played").state == STATE_UNAVAILABLE

    mock_nyt_games_client.get_latest_stats.side_effect = None

    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wordle_played").state != STATE_UNAVAILABLE


async def test_new_account(
    hass: HomeAssistant,
    mock_nyt_games_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test handling an exception during update."""
    mock_nyt_games_client.get_latest_stats.return_value = WordleStats.from_json(
        load_fixture("new_account.json", DOMAIN)
    ).player.stats
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.spelling_bee_played") is None
