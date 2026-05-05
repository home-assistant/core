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
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    assert_trigger_options_supported,
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

    Only states with volume attributes are used as other_states, because
    entities without volume attributes are excluded from all/last checks
    and would cause those tests to fire prematurely.

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
            # States with muted attribute (not muted)
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: False}),
            # States with volume attribute (not muted)
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 1}),
            # States with muted and volume attribute (not muted)
            (
                MediaPlayerState.PLAYING,
                {ATTR_MEDIA_VOLUME_LEVEL: 1, ATTR_MEDIA_VOLUME_MUTED: False},
            ),
        ],
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("media_player.muted", {}, True, True),
        ("media_player.paused_playing", {}, True, True),
        ("media_player.started_playing", {}, True, True),
        ("media_player.stopped_playing", {}, True, True),
        ("media_player.turned_off", {}, True, True),
        ("media_player.turned_on", {}, True, True),
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


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_muted_trigger_ignores_entities_without_volume_attributes(
    hass: HomeAssistant,
) -> None:
    """Test that the muted trigger does not fire for entities without volume attributes."""
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
async def test_muted_trigger_fires_when_entity_gains_volume_attributes(
    hass: HomeAssistant,
) -> None:
    """Test that the trigger fires when an entity gains volume attributes and becomes muted."""
    entity_id = "media_player.gains_volume"
    calls: list[str] = []

    # Start without volume attributes
    hass.states.async_set(entity_id, MediaPlayerState.PLAYING, {})
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        "media_player.muted",
        None,
        {CONF_ENTITY_ID: [entity_id]},
        calls,
    )

    # Gain volume attributes and become muted in one transition
    hass.states.async_set(
        entity_id, MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: True}
    )
    await hass.async_block_till_done()
    assert len(calls) == 1


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_muted_trigger_last_skips_entities_without_volume_attributes(
    hass: HomeAssistant,
) -> None:
    """Test that 'last' behavior skips entities without volume attributes.

    With entities a (has volume), b (has volume), c (no volume):
    The trigger should fire when both a and b are muted, regardless of c.
    """
    entity_a = "media_player.with_volume_a"
    entity_b = "media_player.with_volume_b"
    entity_c = "media_player.no_volume"
    calls: list[str] = []

    # Set initial states
    hass.states.async_set(
        entity_a, MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: False}
    )
    hass.states.async_set(
        entity_b, MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: False}
    )
    hass.states.async_set(entity_c, MediaPlayerState.PLAYING, {})
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        "media_player.muted",
        {"behavior": "last"},
        {CONF_ENTITY_ID: [entity_a, entity_b, entity_c]},
        calls,
    )

    # Mute entity a — not all mutable entities muted yet
    hass.states.async_set(
        entity_a, MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: True}
    )
    await hass.async_block_till_done()
    assert len(calls) == 0

    # Mute entity b — now all mutable entities are muted, trigger fires
    hass.states.async_set(
        entity_b, MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: True}
    )
    await hass.async_block_till_done()
    assert len(calls) == 1


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_muted_trigger_does_not_fire_on_losing_volume_attributes(
    hass: HomeAssistant,
) -> None:
    """Test that the trigger does not fire when a muted entity loses volume attributes."""
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
