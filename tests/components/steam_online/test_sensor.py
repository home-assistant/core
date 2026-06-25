"""Tests for Steam sensor platform."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.steam_online.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)


@pytest.fixture(autouse=True)
def sensor_only() -> Generator[None]:
    """Enable only the sensor platform."""
    with patch(
        "homeassistant.components.steam_online.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


@pytest.mark.usefixtures("steam_api")
async def test_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the Steam sensor platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.freeze_time
async def test_game_icons_cache_eviction(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    steam_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test game icons are evicted from cache and updated."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    states = hass.states.get("sensor.steam_testaccount1")
    assert states
    assert "746d1cd48fb2e57d579b05b6e9eccba95859e549" in states.attributes["game_icon"]

    steam_api.return_value.GetOwnedGames.return_value = (
        await async_load_json_object_fixture(hass, "GetOwnedGames2.json", DOMAIN)
    )

    freezer.tick(timedelta(hours=24))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    states = hass.states.get("sensor.steam_testaccount1")
    assert states
    assert "f6c2ce13796844750dfbd01685fb009eeac4bf70" in states.attributes["game_icon"]
