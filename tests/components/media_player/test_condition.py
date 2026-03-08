"""Test media player conditions."""

from typing import Any

import pytest

from homeassistant.components.media_player.const import MediaPlayerState
from homeassistant.core import HomeAssistant

from tests.components import (
    ConditionStateDescription,
    assert_condition_gated_by_labs_flag,
    create_target_condition,
    other_states,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_media_players(hass: HomeAssistant) -> list[str]:
    """Create multiple media player entities associated with different targets."""
    return (await target_entities(hass, "media_player"))["included"]


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
    target_media_players: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the media player state condition with the 'any' behavior."""
    other_entity_ids = set(target_media_players) - {entity_id}

    # Set all media players, including the tested media player, to the initial state
    for eid in target_media_players:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="any",
    )

    for state in states:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]

        # Check if changing other media players also passes the condition
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]


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
    target_media_players: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the media player state condition with the 'all' behavior."""
    other_entity_ids = set(target_media_players) - {entity_id}

    # Set all media players, including the tested media player, to the initial state
    for eid in target_media_players:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="all",
    )

    for state in states:
        included_state = state["included"]

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert condition(hass) == state["condition_true_first_entity"]

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()

        assert condition(hass) == state["condition_true"]
