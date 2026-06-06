"""Test media player conditions."""

from typing import Any

import pytest

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
)
from homeassistant.components.media_player.const import MediaPlayerState
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    assert_condition_options_supported,
    other_states,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_numerical_attribute_condition_above_below_all,
    parametrize_numerical_attribute_condition_above_below_any,
    parametrize_target_entities,
    target_entities,
)

# Volume is stored as 0.0-1.0 but the threshold is in percent.
_VOLUME_VALUE_SCALE = 0.01

_IS_VOLUME_THRESHOLD = {"threshold": {"type": "above", "value": {"number": 50}}}

# is_muted=True states (mute attr True OR volume_level == 0)
_IS_MUTED_STATES = [
    (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: True}),
    (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 0}),
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
]

# is_muted=False states (mute attr False/missing AND volume_level != 0)
_IS_NOT_MUTED_STATES = [
    (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: False}),
    (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 1}),
    (
        MediaPlayerState.PLAYING,
        {ATTR_MEDIA_VOLUME_LEVEL: 1, ATTR_MEDIA_VOLUME_MUTED: False},
    ),
]


def parametrize_muted_condition_states_any(
    condition: str, target_muted: bool
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize behavior=any condition states for is_muted/is_unmuted."""
    return parametrize_condition_states_any(
        condition=condition,
        target_states=_IS_MUTED_STATES if target_muted else _IS_NOT_MUTED_STATES,
        other_states=_IS_NOT_MUTED_STATES if target_muted else _IS_MUTED_STATES,
        extra_excluded_states=[
            # State without any volume attributes — filtered by _should_include
            MediaPlayerState.PLAYING,
        ],
    )


def parametrize_muted_condition_states_all(
    condition: str, target_muted: bool
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize behavior=all condition states for is_muted/is_unmuted."""
    return parametrize_condition_states_all(
        condition=condition,
        target_states=_IS_MUTED_STATES if target_muted else _IS_NOT_MUTED_STATES,
        other_states=_IS_NOT_MUTED_STATES if target_muted else _IS_MUTED_STATES,
        extra_excluded_states=[
            # State without any volume attributes — filtered by _should_include
            MediaPlayerState.PLAYING,
        ],
    )


@pytest.fixture
async def target_media_players(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple media player entities associated with different targets."""
    return await target_entities(hass, "media_player")


@pytest.mark.parametrize(
    "condition",
    [
        "media_player.is_muted",
        "media_player.is_off",
        "media_player.is_on",
        "media_player.is_not_playing",
        "media_player.is_paused",
        "media_player.is_playing",
        "media_player.is_unmuted",
        "media_player.is_volume",
    ],
)
async def test_media_player_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the media player conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("media_player.is_muted", {}, True, True),
        ("media_player.is_off", {}, True, True),
        ("media_player.is_on", {}, True, True),
        ("media_player.is_not_playing", {}, True, True),
        ("media_player.is_paused", {}, True, True),
        ("media_player.is_playing", {}, True, True),
        ("media_player.is_unmuted", {}, True, True),
        ("media_player.is_volume", _IS_VOLUME_THRESHOLD, True, True),
    ],
)
async def test_media_player_condition_options_validation(
    hass: HomeAssistant,
    condition_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that media_player conditions support the expected options."""
    await assert_condition_options_supported(
        hass,
        condition_key,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_muted_condition_states_any(
            "media_player.is_muted", target_muted=True
        ),
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
        *parametrize_muted_condition_states_any(
            "media_player.is_unmuted", target_muted=False
        ),
        *parametrize_numerical_attribute_condition_above_below_any(
            "media_player.is_volume",
            MediaPlayerState.PLAYING,
            ATTR_MEDIA_VOLUME_LEVEL,
            attribute_required=True,
            attribute_value_scale=_VOLUME_VALUE_SCALE,
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
        *parametrize_muted_condition_states_all(
            "media_player.is_muted", target_muted=True
        ),
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
        *parametrize_muted_condition_states_all(
            "media_player.is_unmuted", target_muted=False
        ),
        *parametrize_numerical_attribute_condition_above_below_all(
            "media_player.is_volume",
            MediaPlayerState.PLAYING,
            ATTR_MEDIA_VOLUME_LEVEL,
            attribute_required=True,
            attribute_value_scale=_VOLUME_VALUE_SCALE,
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
