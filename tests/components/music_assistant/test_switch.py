"""Test Music Assistant switch entities."""

from unittest.mock import MagicMock, call, patch

from music_assistant_models.enums import EventType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.music_assistant.const import DOMAIN
from homeassistant.components.music_assistant.switch import PLAYER_OPTIONS_SWITCH
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    CommonServiceArgument,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import LOCALE_EN, async_get_translations

from .common import (
    create_player_queues_from_fixture,
    setup_integration_from_fixtures,
    snapshot_music_assistant_entities,
    trigger_subscription_callback,
)


@pytest.mark.parametrize("schema_version", [1, 101])
async def test_switch_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    music_assistant_client: MagicMock,
    schema_version: int,
) -> None:
    """Test switch entities, with the queue switches on servers that support them."""
    music_assistant_client.server_info.schema_version = schema_version
    await setup_integration_from_fixtures(hass, music_assistant_client)
    snapshot_music_assistant_entities(hass, entity_registry, snapshot, Platform.SWITCH)


async def test_switch_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test switch set action."""
    mass_player_id = "00:00:00:00:00:01"
    mass_option_key = "enhancer"
    entity_id = "switch.test_player_1_enhancer"

    await setup_integration_from_fixtures(hass, music_assistant_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    # toggle off -> on and verify, that client got called once with correct parameters
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TOGGLE,
        {CommonServiceArgument.ENTITY_ID: entity_id},
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/set_option",
        player_id=mass_player_id,
        option_key=mass_option_key,
        option_value=True,
    )


async def test_external_update(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test external value update."""
    mass_player_id = "00:00:00:00:00:01"
    mass_option_key = "enhancer"
    entity_id = "switch.test_player_1_enhancer"

    await setup_integration_from_fixtures(hass, music_assistant_client)

    # get current option and remove it
    switch_option = next(
        option
        for option in music_assistant_client.players._players[mass_player_id].options
        if option.key == mass_option_key
    )
    music_assistant_client.players._players[mass_player_id].options.remove(
        switch_option
    )

    # set new value different from previous one
    previous_value = switch_option.value
    assert isinstance(previous_value, bool)
    switch_option.value = not previous_value
    music_assistant_client.players._players[mass_player_id].options.append(
        switch_option
    )

    # verify old HA state before trigger
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PLAYER_OPTIONS_UPDATED, mass_player_id
    )

    # verify new HA state after trigger
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON


async def test_ignored(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that non-compatible player options are ignored."""
    config_entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    registry_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry_id=config_entry.entry_id
    )
    # only enhancer and status_light are available
    assert sum(1 for entry in registry_entries if entry.domain == SWITCH_DOMAIN) == 2


async def test_disabled_by_default(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a player option disabled by default is registered disabled."""
    entity_id = "switch.test_player_1_status_light"

    await setup_integration_from_fixtures(hass, music_assistant_client)

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None


async def test_name_translation_availability(
    hass: HomeAssistant,
) -> None:
    """Verify available translation keys are in strings.json."""
    # verify, that PLAYER_OPTIONS_TRANSLATION_KEYS_SWITCH matches strings.json
    translations = await async_get_translations(
        hass, language=LOCALE_EN, category="entity", integrations=[DOMAIN]
    )
    prefix = f"component.{DOMAIN}.entity.{Platform.SWITCH.value}."
    for translation_key in PLAYER_OPTIONS_SWITCH:
        assert translations.get(f"{prefix}{translation_key}.name") is not None, (
            f"{translation_key} is missing in strings.json for platform switch"
        )


@pytest.mark.parametrize(
    ("entity_id", "command", "argument"),
    [
        (
            "switch.test_player_1_crossfade",
            "player_queues/crossfade",
            "crossfade_enabled",
        ),
        (
            "switch.test_player_1_autoplay",
            "player_queues/autoplay",
            "autoplay_enabled",
        ),
    ],
)
@pytest.mark.parametrize(
    ("service", "enabled"),
    [(SwitchService.TURN_ON, True), (SwitchService.TURN_OFF, False)],
)
async def test_queue_switch_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    entity_id: str,
    command: str,
    argument: str,
    service: str,
    enabled: bool,
) -> None:
    """Test a queue switch sets the setting of the player's own queue."""
    music_assistant_client.server_info.schema_version = 101
    await setup_integration_from_fixtures(hass, music_assistant_client)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {CommonServiceArgument.ENTITY_ID: entity_id},
        blocking=True,
    )
    assert music_assistant_client.send_command.call_args == call(
        command, queue_id="00:00:00:00:00:01", **{argument: enabled}, require_schema=101
    )


async def test_queue_switch_follows_queue(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test a queue switch follows its queue, from the moment the server adds it."""
    music_assistant_client.server_info.schema_version = 101
    # the server registers the player before its queue
    with patch(
        "tests.components.music_assistant.common.create_player_queues_from_fixture",
        return_value=[],
    ):
        await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "switch.test_player_1_crossfade"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE

    queue = {queue.queue_id: queue for queue in create_player_queues_from_fixture()}[
        "00:00:00:00:00:01"
    ]
    queue.crossfade_enabled = True
    music_assistant_client.player_queues._queues[queue.queue_id] = queue
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.QUEUE_ADDED, queue.queue_id
    )
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    queue.crossfade_enabled = False
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.QUEUE_UPDATED, queue.queue_id
    )
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
