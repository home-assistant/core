"""Test media player trigger."""

from typing import Any

import pytest

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    MediaPlayerState,
)
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.components.common import (
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_behavior_all,
    assert_trigger_behavior_each,
    assert_trigger_behavior_first,
    assert_trigger_gated_by_labs_flag,
    assert_trigger_ignores_limit_entities_with_wrong_unit,
    assert_trigger_options_supported,
    parametrize_numerical_attribute_changed_trigger_states,
    parametrize_numerical_attribute_crossed_threshold_trigger_states,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)

_VOLUME_CHANGED_THRESHOLD = {"threshold": {"type": "any"}}
_VOLUME_CROSSED_THRESHOLD = {"threshold": {"type": "above", "value": {"number": 50}}}


@pytest.fixture
async def target_media_players(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple media player entities associated with different targets."""
    return await target_entities(hass, "media_player")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "media_player.muted",
        "media_player.unmuted",
        "media_player.volume_changed",
        "media_player.volume_crossed_threshold",
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


def parametrize_muted_trigger_states(
    trigger: str, target_muted: bool
) -> list[tuple[str, dict[str, Any], list[TriggerStateDescription]]]:
    """Parametrize states and expected service call counts for muted/unmuted.

    `target_muted` selects which side fires: True for `media_player.muted`,
    False for `media_player.unmuted`. The helper swaps target / other state
    sets accordingly.

    States without any volume attributes are passed as
    `extra_excluded_states` because
    `_MediaPlayerMutedStateTriggerBase._should_include` filters them out of
    the all/count checks.

    Returns a list of tuples with (trigger, trigger_options, list of states).
    """
    return parametrize_trigger_states(
        trigger=trigger,
        target_states=_IS_MUTED_STATES if target_muted else _IS_NOT_MUTED_STATES,
        other_states=_IS_NOT_MUTED_STATES if target_muted else _IS_MUTED_STATES,
        extra_excluded_states=[
            # State without any volume attributes — filtered by _should_include
            MediaPlayerState.PLAYING,
        ],
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("media_player.muted", {}, True, True),
        ("media_player.unmuted", {}, True, True),
        ("media_player.paused_playing", {}, True, True),
        ("media_player.started_playing", {}, True, True),
        ("media_player.stopped_playing", {}, True, True),
        ("media_player.turned_off", {}, True, True),
        ("media_player.turned_on", {}, True, True),
        ("media_player.volume_changed", _VOLUME_CHANGED_THRESHOLD, False, False),
        (
            "media_player.volume_crossed_threshold",
            _VOLUME_CROSSED_THRESHOLD,
            True,
            True,
        ),
    ],
)
async def test_media_player_trigger_options_validation(
    hass: HomeAssistant,
    trigger_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that media_player triggers support the expected options."""
    await assert_trigger_options_supported(
        hass,
        trigger_key,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_muted_trigger_states("media_player.muted", target_muted=True),
        *parametrize_muted_trigger_states("media_player.unmuted", target_muted=False),
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
async def test_media_player_state_trigger_behavior_each(
    hass: HomeAssistant,
    target_media_players: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test media player state trigger fires for any state change."""
    await assert_trigger_behavior_each(
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
        *parametrize_muted_trigger_states("media_player.muted", target_muted=True),
        *parametrize_muted_trigger_states("media_player.unmuted", target_muted=False),
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
    """Test media player state trigger fires on first entity change."""
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
        *parametrize_muted_trigger_states("media_player.muted", target_muted=True),
        *parametrize_muted_trigger_states("media_player.unmuted", target_muted=False),
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
async def test_media_player_state_trigger_behavior_all(
    hass: HomeAssistant,
    target_media_players: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test media player state trigger fires when all entities have changed."""
    await assert_trigger_behavior_all(
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
        *parametrize_numerical_attribute_changed_trigger_states(
            "media_player.volume_changed",
            MediaPlayerState.PLAYING,
            ATTR_MEDIA_VOLUME_LEVEL,
            attribute_value_scale=0.01,
            attribute_required=True,
        ),
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "media_player.volume_crossed_threshold",
            MediaPlayerState.PLAYING,
            ATTR_MEDIA_VOLUME_LEVEL,
            attribute_value_scale=0.01,
            attribute_required=True,
        ),
    ],
)
async def test_media_player_volume_trigger_behavior_each(
    hass: HomeAssistant,
    target_media_players: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test the media_player volume triggers fire when any entity matches."""
    await assert_trigger_behavior_each(
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
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "media_player.volume_crossed_threshold",
            MediaPlayerState.PLAYING,
            ATTR_MEDIA_VOLUME_LEVEL,
            attribute_value_scale=0.01,
            attribute_required=True,
        ),
    ],
)
async def test_media_player_volume_trigger_behavior_first(
    hass: HomeAssistant,
    target_media_players: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test volume crossed threshold trigger fires for first entity."""
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
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "media_player.volume_crossed_threshold",
            MediaPlayerState.PLAYING,
            ATTR_MEDIA_VOLUME_LEVEL,
            attribute_value_scale=0.01,
            attribute_required=True,
        ),
    ],
)
async def test_media_player_volume_trigger_behavior_all(
    hass: HomeAssistant,
    target_media_players: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test volume crossed threshold trigger fires for last entity."""
    await assert_trigger_behavior_all(
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
    ("trigger", "trigger_options", "limit_entities"),
    [
        (
            "media_player.volume_changed",
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "sensor.volume_above"},
                    "value_max": {"entity": "sensor.volume_below"},
                },
            },
            ["sensor.volume_above", "sensor.volume_below"],
        ),
        (
            "media_player.volume_crossed_threshold",
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "sensor.volume_lower"},
                    "value_max": {"entity": "sensor.volume_upper"},
                },
            },
            ["sensor.volume_lower", "sensor.volume_upper"],
        ),
    ],
)
async def test_media_player_trigger_ignores_limit_entity_with_wrong_unit(
    hass: HomeAssistant,
    trigger: str,
    trigger_options: dict[str, Any],
    limit_entities: list[str],
) -> None:
    """Test numerical triggers do not fire if limit entities have the wrong unit."""
    await assert_trigger_ignores_limit_entities_with_wrong_unit(
        hass,
        trigger=trigger,
        trigger_options=trigger_options,
        entity_id="media_player.test_player",
        reset_state={
            "state": MediaPlayerState.PLAYING,
            "attributes": {ATTR_MEDIA_VOLUME_LEVEL: 0.0},
        },
        trigger_state={
            "state": MediaPlayerState.PLAYING,
            "attributes": {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        },
        limit_entities=[
            (limit_entities[0], "10"),
            (limit_entities[1], "90"),
        ],
        correct_unit="%",
        wrong_unit="lx",
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_muted_trigger_ignores_entities_without_volume_attributes(
    hass: HomeAssistant,
) -> None:
    """Test muted trigger ignores entities without volume attributes."""
    entity_id = "media_player.no_volume"
    calls: list[str] = []

    hass.states.async_set(entity_id, MediaPlayerState.PLAYING, {})
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        "media_player.muted",
        None,
        {CONF_ENTITY_ID: [entity_id]},
        calls,
    )

    # Transition without volume attributes — should not fire
    hass.states.async_set(entity_id, MediaPlayerState.IDLE, {})
    await hass.async_block_till_done()
    assert len(calls) == 0

    # Transition with volume attributes — should not fire (not muted)
    hass.states.async_set(
        entity_id, MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: False}
    )
    await hass.async_block_till_done()
    assert len(calls) == 0

    # Transition to muted — should fire
    hass.states.async_set(
        entity_id, MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: True}
    )
    await hass.async_block_till_done()
    assert len(calls) == 1


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_muted_trigger_does_not_fire_on_losing_volume_attributes(
    hass: HomeAssistant,
) -> None:
    """Test trigger skips when muted entity loses volume attributes."""
    entity_id = "media_player.loses_volume"
    calls: list[str] = []

    # Start muted
    hass.states.async_set(
        entity_id, MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: True}
    )
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        "media_player.muted",
        None,
        {CONF_ENTITY_ID: [entity_id]},
        calls,
    )

    # Lose volume attributes — should not fire (transition to no-attributes
    # is not a valid transition because to_state has no volume attributes)
    hass.states.async_set(entity_id, MediaPlayerState.PLAYING, {})
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_unmuted_trigger_does_not_fire_when_entity_gains_volume_attributes(
    hass: HomeAssistant,
) -> None:
    """Test unmuted trigger skips when entity gains volume attrs already-unmuted.

    `is_muted` defaults to False for a state without volume attributes, so a
    transition `(PLAYING, {})` -> `(PLAYING, {muted=False})` keeps `is_muted`
    at False — `is_valid_transition` rejects it and the unmuted trigger
    must stay silent. The shared muted/unmuted helper iterates entity_id
    through the firing transitions for both sides via `_IS_MUTED_STATES`
    and `_IS_NOT_MUTED_STATES`; this dedicated test covers the inverse
    no-attrs-as-initial case for unmuted, which the helper does not
    exercise on its own.
    """
    entity_id = "media_player.gains_volume"
    calls: list[str] = []

    # Start without volume attributes
    hass.states.async_set(entity_id, MediaPlayerState.PLAYING, {})
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        "media_player.unmuted",
        None,
        {CONF_ENTITY_ID: [entity_id]},
        calls,
    )

    # Gain volume attributes already-unmuted — must not fire
    hass.states.async_set(
        entity_id, MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: False}
    )
    await hass.async_block_till_done()
    assert len(calls) == 0
