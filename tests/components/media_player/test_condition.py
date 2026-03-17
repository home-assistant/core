"""Test media player conditions."""

from typing import Any

import pytest

from homeassistant.components.media_player.const import MediaPlayerState
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    other_states,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    target_entities,
)


@pytest.fixture
async def target_media_players(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple media player entities associated with different targets."""
    return await target_entities(hass, "media_player")


@pytest.mark.parametrize(
    "condition",
    [
        "media_player.is_off",
        "media_player.is_on",
        "media_player.is_not_playing",
        "media_player.is_paused",
        "media_player.is_playing",
    ],
)
async def test_media_player_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the media player conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="media_player.is_off",
            target_states=[MediaPlayerState.OFF],
            other_states=other_states(MediaPlayerState.OFF),
        ),
        *parametrize_condition_states_any(
            condition="media_player.is_on",
            target_states=[
                MediaPlayerState.BUFFERING,
                MediaPlayerState.IDLE,
                MediaPlayerState.ON,
                MediaPlayerState.PAUSED,
                MediaPlayerState.PLAYING,
            ],
            other_states=[MediaPlayerState.OFF],
        ),
        *parametrize_condition_states_any(
            condition="media_player.is_not_playing",
            target_states=[
                MediaPlayerState.BUFFERING,
                MediaPlayerState.IDLE,
                MediaPlayerState.OFF,
                MediaPlayerState.ON,
                MediaPlayerState.PAUSED,
            ],
            other_states=[MediaPlayerState.PLAYING],
        ),
        *parametrize_condition_states_any(
            condition="media_player.is_paused",
            target_states=[MediaPlayerState.PAUSED],
            other_states=other_states(MediaPlayerState.PAUSED),
        ),
        *parametrize_condition_states_any(
            condition="media_player.is_playing",
            target_states=[MediaPlayerState.PLAYING],
            other_states=other_states(MediaPlayerState.PLAYING),
        ),
    ],
)
async def test_media_player_state_condition_behavior_any(
    hass: HomeAssistant,
    target_media_players: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the media player state condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_media_players,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="media_player.is_off",
            target_states=[MediaPlayerState.OFF],
            other_states=other_states(MediaPlayerState.OFF),
        ),
        *parametrize_condition_states_all(
            condition="media_player.is_on",
            target_states=[
                MediaPlayerState.BUFFERING,
                MediaPlayerState.IDLE,
                MediaPlayerState.ON,
                MediaPlayerState.PAUSED,
                MediaPlayerState.PLAYING,
            ],
            other_states=[MediaPlayerState.OFF],
        ),
        *parametrize_condition_states_all(
            condition="media_player.is_not_playing",
            target_states=[
                MediaPlayerState.BUFFERING,
                MediaPlayerState.IDLE,
                MediaPlayerState.OFF,
                MediaPlayerState.ON,
                MediaPlayerState.PAUSED,
            ],
            other_states=[MediaPlayerState.PLAYING],
        ),
        *parametrize_condition_states_all(
            condition="media_player.is_paused",
            target_states=[MediaPlayerState.PAUSED],
            other_states=other_states(MediaPlayerState.PAUSED),
        ),
        *parametrize_condition_states_all(
            condition="media_player.is_playing",
            target_states=[MediaPlayerState.PLAYING],
            other_states=other_states(MediaPlayerState.PLAYING),
        ),
    ],
)
async def test_media_player_state_condition_behavior_all(
    hass: HomeAssistant,
    target_media_players: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the media player state condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_media_players,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
