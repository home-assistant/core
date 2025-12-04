"""Test media player trigger."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    MediaPlayerState,
)
from homeassistant.const import (
    ATTR_LABEL_ID,
    CONF_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.components import (
    StateDescription,
    arm_trigger,
    parametrize_target_entities,
    parametrize_trigger_states,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture(name="enable_experimental_triggers_conditions")
def enable_experimental_triggers_conditions() -> Generator[None]:
    """Enable experimental triggers and conditions."""
    with patch(
        "homeassistant.components.labs.async_is_preview_feature_enabled",
        return_value=True,
    ):
        yield


@pytest.fixture
async def target_media_players(hass: HomeAssistant) -> list[str]:
    """Create multiple media player entities associated with different targets."""
    return (await target_entities(hass, "media_player"))["included"]


@pytest.mark.parametrize(
    "trigger_key",
    [
        "media_player.stopped_playing",
    ],
)
async def test_media_player_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the media player triggers are gated by the labs flag."""
    await arm_trigger(hass, trigger_key, None, {ATTR_LABEL_ID: "test_label"})
    assert (
        "Unnamed automation failed to setup triggers and has been disabled: Trigger "
        f"'{trigger_key}' requires the experimental 'New triggers and conditions' "
        "feature to be enabled in Home Assistant Labs settings (feature flag: "
        "'new_triggers_conditions')"
    ) in caplog.text


def parametrize_muted_unmuted_trigger_states(
    trigger: str,
    target_state: tuple[str, dict],
    other_state: tuple[str, dict],
) -> list[
    tuple[str, tuple[str | None, dict], list[tuple[tuple[str | None, dict], int]]]
]:
    """Parametrize states and expected service call counts.

    Returns a list of tuples with (trigger, initial_state, list of states), where
    states is a list of tuples
    (state to set, expected service call count).
    """
    return [
        # Initial state None
        (
            trigger,
            (None, {}),
            [
                (target_state, 0),
                (other_state, 0),
                (target_state, 1),
            ],
        ),
        # Initial state different from target state
        (
            trigger,
            other_state,
            [
                (target_state, 1),
                (other_state, 0),
                (target_state, 1),
            ],
        ),
        # Initial state same as target state
        (
            trigger,
            target_state,
            [
                (target_state, 0),
                (other_state, 0),
                (target_state, 1),
            ],
        ),
        # Initial state unavailable / unknown
        (
            trigger,
            (STATE_UNAVAILABLE, {}),
            [
                (target_state, 0),
                (other_state, 0),
                (target_state, 1),
            ],
        ),
        (
            trigger,
            (STATE_UNKNOWN, {}),
            [
                (target_state, 0),
                (other_state, 0),
                (target_state, 1),
            ],
        ),
    ]


def parametrize_muted_trigger_states() -> list[
    tuple[str, tuple[str | None, dict], list[tuple[tuple[str | None, dict], int]]]
]:
    """Parametrize states and expected service call counts.

    Returns a list of tuples with (trigger, initial_state, list of states), where
    states is a list of tuples (state to set, expected service call count).
    """
    trigger = "media_player.muted"
    return [
        # States with muted attribute
        *parametrize_muted_unmuted_trigger_states(
            trigger,
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: True}),
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: False}),
        ),
        *parametrize_muted_unmuted_trigger_states(
            trigger,
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: True}),
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: None}),
        ),
        *parametrize_muted_unmuted_trigger_states(
            trigger,
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_MUTED: True}),
            (MediaPlayerState.PLAYING, {}),  # Missing attribute
        ),
        # States with volume attribute
        *parametrize_muted_unmuted_trigger_states(
            trigger,
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 0}),
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 1}),
        ),
        *parametrize_muted_unmuted_trigger_states(
            trigger,
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 0}),
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: None}),
        ),
        *parametrize_muted_unmuted_trigger_states(
            trigger,
            (MediaPlayerState.PLAYING, {ATTR_MEDIA_VOLUME_LEVEL: 0}),
            (MediaPlayerState.PLAYING, {}),  # Missing attribute
        ),
        # States with muted and volume attribute
        *parametrize_muted_unmuted_trigger_states(
            trigger,
            (
                MediaPlayerState.PLAYING,
                {ATTR_MEDIA_VOLUME_LEVEL: 0, ATTR_MEDIA_VOLUME_MUTED: True},
            ),
            (
                MediaPlayerState.PLAYING,
                {ATTR_MEDIA_VOLUME_LEVEL: 1, ATTR_MEDIA_VOLUME_MUTED: False},
            ),
        ),
        *parametrize_muted_unmuted_trigger_states(
            trigger,
            (
                MediaPlayerState.PLAYING,
                {ATTR_MEDIA_VOLUME_LEVEL: 0, ATTR_MEDIA_VOLUME_MUTED: False},
            ),
            (
                MediaPlayerState.PLAYING,
                {ATTR_MEDIA_VOLUME_LEVEL: 1, ATTR_MEDIA_VOLUME_MUTED: False},
            ),
        ),
        *parametrize_muted_unmuted_trigger_states(
            trigger,
            (
                MediaPlayerState.PLAYING,
                {ATTR_MEDIA_VOLUME_LEVEL: 1, ATTR_MEDIA_VOLUME_MUTED: True},
            ),
            (
                MediaPlayerState.PLAYING,
                {ATTR_MEDIA_VOLUME_LEVEL: 1, ATTR_MEDIA_VOLUME_MUTED: False},
            ),
        ),
    ]


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
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
async def test_media_player_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_media_players: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[StateDescription],
) -> None:
    """Test that the media player state trigger fires when any media player state changes to a specific state."""
    await async_setup_component(hass, "media_player", {})

    other_entity_ids = set(target_media_players) - {entity_id}

    # Set all media players, including the tested media player, to the initial state
    for eid in target_media_players:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other media players also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("trigger", "initial_state", "states"),
    [
        *parametrize_muted_trigger_states(),
    ],
)
async def test_media_player_state_attribute_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_media_players: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    initial_state: tuple[str | None, dict],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the media player state trigger fires when any media player state changes to a specific state."""
    await async_setup_component(hass, "media player", {})

    other_entity_ids = set(target_media_players) - {entity_id}

    # Set all media players, including the tested media player, to the initial state
    for eid in target_media_players:
        set_or_remove_state(
            hass, eid, {"state": initial_state[0], "attributes": initial_state[1]}
        )
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {}, trigger_target_config)

    for state, expected_calls in states:
        set_or_remove_state(
            hass, entity_id, {"state": state[0], "attributes": state[1]}
        )
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other media players also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(
                hass, other_entity_id, {"state": state[0], "attributes": state[1]}
            )
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * expected_calls
        service_calls.clear()


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
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
    service_calls: list[ServiceCall],
    target_media_players: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[StateDescription],
) -> None:
    """Test that the media player state trigger fires when the first media player changes to a specific state."""
    await async_setup_component(hass, "media_player", {})

    other_entity_ids = set(target_media_players) - {entity_id}

    # Set all media players, including the tested media player, to the initial state
    for eid in target_media_players:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "first"}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other media players should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("trigger", "initial_state", "states"),
    [
        *parametrize_muted_trigger_states(),
    ],
)
async def test_media_player_state_attribute_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_media_players: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    initial_state: tuple[str | None, dict],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the media player state trigger fires when the first media player state changes to a specific state."""
    await async_setup_component(hass, "media_player", {})

    other_entity_ids = set(target_media_players) - {entity_id}

    # Set all media players, including the tested media player, to the initial state
    for eid in target_media_players:
        set_or_remove_state(
            hass, eid, {"state": initial_state[0], "attributes": initial_state[1]}
        )
        await hass.async_block_till_done()

    await arm_trigger(
        hass,
        trigger,
        {"behavior": "first"},
        trigger_target_config,
    )

    for state, expected_calls in states:
        set_or_remove_state(
            hass, entity_id, {"state": state[0], "attributes": state[1]}
        )
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other media players should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(
                hass, other_entity_id, {"state": state[0], "attributes": state[1]}
            )
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
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
    service_calls: list[ServiceCall],
    target_media_players: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[StateDescription],
) -> None:
    """Test that the media player state trigger fires when the last media player changes to a specific state."""
    await async_setup_component(hass, "media_player", {})

    other_entity_ids = set(target_media_players) - {entity_id}

    # Set all media players, including the tested media player, to the initial state
    for eid in target_media_players:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "last"}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("trigger", "initial_state", "states"),
    [
        *parametrize_muted_trigger_states(),
    ],
)
async def test_media_player_state_attribute_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_media_players: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    initial_state: tuple[str | None, dict],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the media player state trigger fires when the last media player state changes to a specific state."""
    await async_setup_component(hass, "media_player", {})

    other_entity_ids = set(target_media_players) - {entity_id}

    # Set all media players, including the tested media player, to the initial state
    for eid in target_media_players:
        set_or_remove_state(
            hass, eid, {"state": initial_state[0], "attributes": initial_state[1]}
        )
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "last"}, trigger_target_config)

    for state, expected_calls in states:
        for other_entity_id in other_entity_ids:
            set_or_remove_state(
                hass, other_entity_id, {"state": state[0], "attributes": state[1]}
            )
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(
            hass, entity_id, {"state": state[0], "attributes": state[1]}
        )
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()
