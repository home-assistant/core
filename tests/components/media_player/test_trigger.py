"""Test media player trigger."""

from typing import Any

import pytest

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant

from tests.components.common import (
    TriggerStateDescription,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    parametrize_target_entities,
    parametrize_trigger_states,
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
        *parametrize_muted_trigger_states(),
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
