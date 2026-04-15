"""Test media player trigger."""

from typing import Any

import pytest

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.components.common import (
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    parametrize_target_entities,
    parametrize_trigger_states,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_media_players(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple media player entities associated with different targets."""
    return await target_entities(hass, "media_player")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "media_player.muted",
        "media_player.paused_playing",
        "media_player.started_playing",
        "media_player.stopped_playing",
        "media_player.turned_off",
        "media_player.turned_on",
    ],
)
async def test_media_player_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the media player triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


def parametrize_muted_trigger_states() -> list[
    tuple[str, list[TriggerStateDescription]]
]:
    """Parametrize states and expected service call counts.

    Returns a list of tuples with (trigger, list of states),
    where states is a list of TriggerStateDescription dicts.
    """
    trigger = "media_player.muted"
    return parametrize_trigger_states(
        trigger=trigger,
        target_states=[
            # States with muted attribute
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: True}),
            # States with volume attribute
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 0}),
            # States with muted and volume attribute
            (
                MediaPlayerState.PLAYING,
                {ATTR_MEDIA_VOLUME_LEVEL: 0, ATTR_MEDIA_VOLUME_MUTED: True},
            ),
            (
                MediaPlayerState.PLAYING,
                {ATTR_MEDIA_VOLUME_LEVEL: 0, ATTR_MEDIA_VOLUME_MUTED: False},
            ),
            (
                MediaPlayerState.PLAYING,
                {ATTR_MEDIA_VOLUME_LEVEL: 1, ATTR_MEDIA_VOLUME_MUTED: True},
            ),
        ],
        other_states=[
            # States with muted attribute
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: False}),
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: None}),
            (MediaPlayerState.PLAYING, {}),  # Missing attribute
            # States with volume attribute
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 1}),
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: None}),
            (MediaPlayerState.PLAYING, {}),  # Missing attribute
            # States with muted and volume attribute
            (
                MediaPlayerState.PLAYING,
                {ATTR_MEDIA_VOLUME_LEVEL: 1, ATTR_MEDIA_VOLUME_MUTED: False},
            ),
        ],
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="media_player.paused_playing",
            target_states=[
                MediaPlayerState.PAUSED,
            ],
            other_states=[
                MediaPlayerState.BUFFERING,
                MediaPlayerState.PLAYING,
            ],
        ),
        *parametrize_trigger_states(
            trigger="media_player.started_playing",
            target_states=[
                MediaPlayerState.BUFFERING,
                MediaPlayerState.PLAYING,
            ],
            other_states=[
                MediaPlayerState.IDLE,
                MediaPlayerState.OFF,
                MediaPlayerState.ON,
                MediaPlayerState.PAUSED,
            ],
        ),
        *parametrize_trigger_states(
            trigger="media_player.stopped_playing",
            target_states=[
                MediaPlayerState.IDLE,
                MediaPlayerState.OFF,
                MediaPlayerState.ON,
            ],
            other_states=[
                MediaPlayerState.BUFFERING,
                MediaPlayerState.PAUSED,
                MediaPlayerState.PLAYING,
            ],
        ),
        *parametrize_trigger_states(
            trigger="media_player.turned_off",
            target_states=[
                MediaPlayerState.OFF,
            ],
            other_states=[
                MediaPlayerState.BUFFERING,
                MediaPlayerState.IDLE,
                MediaPlayerState.ON,
                MediaPlayerState.PAUSED,
                MediaPlayerState.PLAYING,
            ],
        ),
        *parametrize_trigger_states(
            trigger="media_player.turned_on",
            target_states=[
                MediaPlayerState.BUFFERING,
                MediaPlayerState.IDLE,
                MediaPlayerState.ON,
                MediaPlayerState.PAUSED,
                MediaPlayerState.PLAYING,
            ],
            other_states=[
                MediaPlayerState.OFF,
            ],
        ),
    ],
)
async def test_media_player_state_trigger_behavior_any(
    hass: HomeAssistant,
    target_media_players: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the media player state trigger fires when any media player state changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        target_entities=target_media_players,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_muted_trigger_states(),
    ],
)
async def test_media_player_state_attribute_trigger_behavior_any(
    hass: HomeAssistant,
    target_media_players: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the media player state trigger fires when any media player state changes to a specific state."""
    calls: list[str] = []
    await async_setup_component(hass, "media player", {})

    other_entity_ids = set(target_media_players["included_entities"]) - {entity_id}

    # Set all media players, including the tested media player, to the initial state
    for eid in target_media_players["included_entities"]:
        set_or_remove_state(hass, eid, states[0]["included_state"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {}, trigger_target_config, calls)

    for state in states[1:]:
        included_state = state["included_state"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(calls) == state["count"]
        for call in calls:
            assert call == entity_id
        calls.clear()

        # Check if changing other media players also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(calls) == (entities_in_target - 1) * state["count"]
        calls.clear()


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="media_player.stopped_playing",
            target_states=[
                MediaPlayerState.IDLE,
                MediaPlayerState.OFF,
                MediaPlayerState.ON,
            ],
            other_states=[
                MediaPlayerState.BUFFERING,
                MediaPlayerState.PAUSED,
                MediaPlayerState.PLAYING,
            ],
        ),
    ],
)
async def test_media_player_state_trigger_behavior_first(
    hass: HomeAssistant,
    target_media_players: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the media player state trigger fires when the first media player changes to a specific state."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_media_players,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_muted_trigger_states(),
    ],
)
async def test_media_player_state_attribute_trigger_behavior_first(
    hass: HomeAssistant,
    target_media_players: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the media player state trigger fires when the first media player state changes to a specific state."""
    calls: list[str] = []
    await async_setup_component(hass, "media_player", {})

    other_entity_ids = set(target_media_players["included_entities"]) - {entity_id}

    # Set all media players, including the tested media player, to the initial state
    for eid in target_media_players["included_entities"]:
        set_or_remove_state(hass, eid, states[0]["included_state"])
        await hass.async_block_till_done()

    await arm_trigger(
        hass,
        trigger,
        {"behavior": "first"},
        trigger_target_config,
        calls,
    )

    for state in states[1:]:
        included_state = state["included_state"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(calls) == state["count"]
        for call in calls:
            assert call == entity_id
        calls.clear()

        # Triggering other media players should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="media_player.stopped_playing",
            target_states=[
                MediaPlayerState.IDLE,
                MediaPlayerState.OFF,
                MediaPlayerState.ON,
            ],
            other_states=[
                MediaPlayerState.BUFFERING,
                MediaPlayerState.PAUSED,
                MediaPlayerState.PLAYING,
            ],
        ),
    ],
)
async def test_media_player_state_trigger_behavior_last(
    hass: HomeAssistant,
    target_media_players: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the media player state trigger fires when the last media player changes to a specific state."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_media_players,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_muted_trigger_states(),
    ],
)
async def test_media_player_state_attribute_trigger_behavior_last(
    hass: HomeAssistant,
    target_media_players: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the media player state trigger fires when the last media player state changes to a specific state."""
    calls: list[str] = []
    await async_setup_component(hass, "media_player", {})

    other_entity_ids = set(target_media_players["included_entities"]) - {entity_id}

    # Set all media players, including the tested media player, to the initial state
    for eid in target_media_players["included_entities"]:
        set_or_remove_state(hass, eid, states[0]["included_state"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "last"}, trigger_target_config, calls)

    for state in states[1:]:
        included_state = state["included_state"]
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(calls) == 0

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(calls) == state["count"]
        for call in calls:
            assert call == entity_id
        calls.clear()
