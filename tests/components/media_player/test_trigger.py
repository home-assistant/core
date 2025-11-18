"""Test media player trigger."""

import pytest

from homeassistant.components import automation
from homeassistant.components.media_player import MediaPlayerState
from homeassistant.const import CONF_ENTITY_ID, CONF_OPTIONS, CONF_PLATFORM, CONF_TARGET
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.components import (
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
async def target_media_players(hass: HomeAssistant) -> None:
    """Create multiple media player entities associated with different targets."""
    return await target_entities(hass, "media_player")


def set_or_remove_state(
    hass: HomeAssistant,
    entity_id: str,
    state: str | None,
    attributes: dict | None = None,
) -> None:
    """Set or clear the state of an entity."""
    if state is None:
        hass.states.async_remove(entity_id)
    else:
        hass.states.async_set(entity_id, state, attributes, force_update=True)


async def setup_automation(
    hass: HomeAssistant, trigger: str, trigger_options: dict, trigger_target: dict
) -> None:
    """Set up automation component with given config."""
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: trigger,
                    CONF_OPTIONS: {**trigger_options},
                    CONF_TARGET: {**trigger_target},
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {CONF_ENTITY_ID: "{{ trigger.entity_id }}"},
                },
            }
        },
    )


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            "media_player.stopped_playing",
            (MediaPlayerState.IDLE, MediaPlayerState.OFF, MediaPlayerState.ON),
            (
                MediaPlayerState.BUFFERING,
                MediaPlayerState.PAUSED,
                MediaPlayerState.PLAYING,
            ),
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
    states: list[tuple[str, int]],
) -> None:
    """Test that the media player state trigger fires when any media player state changes to a specific state."""
    await async_setup_component(hass, "media_player", {})

    other_entity_ids = set(target_media_players) - {entity_id}

    # Set all media players, including the tested media player, to the initial state
    for eid in target_media_players:
        set_or_remove_state(hass, eid, states[0][0])
        await hass.async_block_till_done()

    await setup_automation(hass, trigger, {}, trigger_target_config)

    for state, expected_calls in states[1:]:
        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other media players also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * expected_calls
        service_calls.clear()


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            "media_player.stopped_playing",
            (MediaPlayerState.IDLE, MediaPlayerState.OFF, MediaPlayerState.ON),
            (
                MediaPlayerState.BUFFERING,
                MediaPlayerState.PAUSED,
                MediaPlayerState.PLAYING,
            ),
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
    states: list[tuple[str, int, list[str]]],
) -> None:
    """Test that the media player state trigger fires when the first media player changes to a specific state."""
    await async_setup_component(hass, "media_player", {})

    other_entity_ids = set(target_media_players) - {entity_id}

    # Set all media players, including the tested media player, to the initial state
    for eid in target_media_players:
        set_or_remove_state(hass, eid, states[0][0])
        await hass.async_block_till_done()

    await setup_automation(hass, trigger, {"behavior": "first"}, trigger_target_config)

    for state, expected_calls in states[1:]:
        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other media players should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("media_player"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            "media_player.stopped_playing",
            (MediaPlayerState.IDLE, MediaPlayerState.OFF, MediaPlayerState.ON),
            (
                MediaPlayerState.BUFFERING,
                MediaPlayerState.PAUSED,
                MediaPlayerState.PLAYING,
            ),
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
    states: list[tuple[str, int]],
) -> None:
    """Test that the media player state trigger fires when the last media player changes to a specific state."""
    await async_setup_component(hass, "media_player", {})

    other_entity_ids = set(target_media_players) - {entity_id}

    # Set all media players, including the tested media player, to the initial state
    for eid in target_media_players:
        set_or_remove_state(hass, eid, states[0][0])
        await hass.async_block_till_done()

    await setup_automation(hass, trigger, {"behavior": "last"}, trigger_target_config)

    for state, expected_calls in states[1:]:
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()
