"""Test the Xbox sensor platform."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from pythonxbox.api.provider.titlehub.models import TitleHubResponse
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.xbox.const import DOMAIN
from homeassistant.components.xbox.sensor import XboxSensor
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def sensor_only() -> Generator[None]:
    """Enable only the sensor platform."""
    with patch(
        "homeassistant.components.xbox.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


@pytest.mark.usefixtures("xbox_live_client", "entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the Xbox sensor platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "key"),
    [
        ("gsr_ae_account_tier", XboxSensor.ACCOUNT_TIER),
        ("gsr_ae_gold_tenure", XboxSensor.GOLD_TENURE),
    ],
)
@pytest.mark.usefixtures("xbox_live_client", "entity_registry_enabled_by_default")
async def test_sensor_deprecation_remove_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    key: XboxSensor,
) -> None:
    """Test we remove a deprecated sensor."""

    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"271958441785640_{key}",
        suggested_object_id=entity_id,
    )

    assert entity_registry is not None

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert entity_registry.async_get(f"sensor.{entity_id}") is None


@pytest.mark.usefixtures("xbox_live_client", "entity_registry_enabled_by_default")
async def test_sensor_recently_played_games(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test recently played games sensor."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    # Trigger a coordinator refresh to populate data
    await config_entry.runtime_data.title_history.async_refresh()
    await hass.async_block_till_done()

    # Verify the sensor was created
    state = hass.states.get("sensor.home_assistant_cloud_recently_played_games")
    assert state is not None
    assert state.state == "2"  # 2 games in the titlehistory fixture

    # Verify attributes contain game data
    assert "games" in state.attributes
    games = state.attributes["games"]
    assert len(games) == 2

    # Verify first game data
    game1 = games[0]
    assert game1["title"] == "Blue Dragon"
    assert game1["title_id"] == "1297287135"
    assert game1["achievements_earned"] == 3
    assert game1["achievements_total"] == 43
    assert game1["gamerscore_earned"] == 15
    assert game1["gamerscore_total"] == 1000
    assert game1["achievement_progress"] == 2
    assert "last_played" in game1

    # Verify second game data
    game2 = games[1]
    assert game2["title"] == "Assassin's Creed® Syndicate"
    assert game2["title_id"] == "1560034050"
    assert game2["achievements_earned"] == 22
    assert game2["gamerscore_total"] == 1300
    assert game2["achievement_progress"] == 36


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_recently_played_games_no_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client,
) -> None:
    """Test recently played games sensor with no game history."""
    # Mock titlehub to return empty response
    xbox_live_client.titlehub.get_title_history.return_value = TitleHubResponse(
        xuid="271958441785640",
        titles=[],
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    # Trigger a coordinator refresh to populate data
    await config_entry.runtime_data.title_history.async_refresh()
    await hass.async_block_till_done()

    # Verify the sensor handles empty data gracefully
    state = hass.states.get("sensor.home_assistant_cloud_recently_played_games")
    assert state is not None
    assert state.state == "0"
    assert state.attributes["games"] == []
