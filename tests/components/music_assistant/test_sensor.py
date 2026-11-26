"""Test Music Assistant sensors."""

from unittest.mock import MagicMock

from music_assistant_models.enums import EventType, SleepTimerMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    setup_integration_from_fixtures,
    snapshot_music_assistant_entities,
    trigger_subscription_callback,
)

END_ENTITY_ID = "sensor.test_player_1_sleep_timer_end"
MODE_ENTITY_ID = "sensor.test_player_1_sleep_timer_mode"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    music_assistant_client: MagicMock,
) -> None:
    """Test sensor entities."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    snapshot_music_assistant_entities(hass, entity_registry, snapshot, Platform.SENSOR)


@pytest.mark.parametrize(
    ("expires_at", "mode", "expected_end", "expected_mode"),
    [
        pytest.param(None, None, STATE_UNKNOWN, "off", id="no_timer"),
        pytest.param(
            1767225600.0,
            SleepTimerMode.DURATION,
            "2026-01-01T00:00:00+00:00",
            "duration",
            id="duration",
        ),
        pytest.param(
            None,
            SleepTimerMode.END_OF_CHAPTER,
            STATE_UNKNOWN,
            "end_of_chapter",
            id="end_of_chapter_paused",
        ),
        pytest.param(
            1767225600.0,
            None,
            "2026-01-01T00:00:00+00:00",
            "duration",
            id="server_without_modes",
        ),
        pytest.param(
            1767225600.0,
            SleepTimerMode.UNKNOWN,
            "2026-01-01T00:00:00+00:00",
            STATE_UNKNOWN,
            id="newer_mode",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sleep_timer_sensors(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    expires_at: float | None,
    mode: SleepTimerMode | None,
    expected_end: str,
    expected_mode: str,
) -> None:
    """Test the sleep timer sensors show the end and mode of the player's timer."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    player = music_assistant_client.players._players["00:00:00:00:00:01"]
    player.sleep_timer_expires_at = expires_at
    player.sleep_timer_mode = mode
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PLAYER_UPDATED, "00:00:00:00:00:01"
    )
    assert hass.states.get(END_ENTITY_ID).state == expected_end
    assert hass.states.get(MODE_ENTITY_ID).state == expected_mode


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sleep_timer_sensors_follow_active_source(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test a player playing along with another one shows that player's sleep timer."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    players = music_assistant_client.players._players
    players["00:00:00:00:00:01"].active_source = "test_group_player_1"
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PLAYER_UPDATED, "00:00:00:00:00:01"
    )
    assert hass.states.get(MODE_ENTITY_ID).state == "off"

    # the timer is set on the player that owns the playback
    group_player = players["test_group_player_1"]
    group_player.sleep_timer_expires_at = 1767225600.0
    group_player.sleep_timer_mode = SleepTimerMode.DURATION
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PLAYER_UPDATED, "test_group_player_1"
    )
    assert hass.states.get(END_ENTITY_ID).state == "2026-01-01T00:00:00+00:00"
    assert hass.states.get(MODE_ENTITY_ID).state == "duration"


async def test_sleep_timer_sensors_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    music_assistant_client: MagicMock,
) -> None:
    """Test the sleep timer sensors are added disabled."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    for entity_id in (END_ENTITY_ID, MODE_ENTITY_ID):
        entry = entity_registry.async_get(entity_id)
        assert entry
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
