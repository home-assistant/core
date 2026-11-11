"""Test Music Assistant number entities."""

from unittest.mock import MagicMock, call, patch

from music_assistant_models.enums import EventType
from music_assistant_models.media_items import Audiobook
from music_assistant_models.queue_item import QueueItem
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.music_assistant.const import DOMAIN
from homeassistant.components.music_assistant.number import PLAYER_OPTIONS_NUMBER
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import LOCALE_EN, async_get_translations

from .common import (
    setup_integration_from_fixtures,
    snapshot_music_assistant_entities,
    trigger_subscription_callback,
)


async def test_number_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    music_assistant_client: MagicMock,
) -> None:
    """Test number entities."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    snapshot_music_assistant_entities(hass, entity_registry, snapshot, Platform.NUMBER)


async def test_number_set_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test number set action."""
    mass_player_id = "00:00:00:00:00:01"
    mass_option_key = "treble"
    entity_id = "number.test_player_1_treble"

    option_value = 3

    await setup_integration_from_fixtures(hass, music_assistant_client)
    state = hass.states.get(entity_id)
    assert state

    # test within range
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_VALUE: option_value,
        },
        blocking=True,
    )

    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/set_option",
        player_id=mass_player_id,
        option_key=mass_option_key,
        option_value=option_value,
    )

    # test out of range
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_VALUE: 20,
            },
            blocking=True,
        )


async def test_external_update(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test external value update."""
    mass_player_id = "00:00:00:00:00:01"
    mass_option_key = "treble"
    entity_id = "number.test_player_1_treble"

    await setup_integration_from_fixtures(hass, music_assistant_client)

    # get current option and remove it
    number_option = next(
        option
        for option in music_assistant_client.players._players[mass_player_id].options
        if option.key == mass_option_key
    )
    music_assistant_client.players._players[mass_player_id].options.remove(
        number_option
    )

    # set new value different from previous one
    previous_value = number_option.value
    new_value = 5
    number_option.value = new_value
    assert previous_value != number_option.value
    music_assistant_client.players._players[mass_player_id].options.append(
        number_option
    )

    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PLAYER_OPTIONS_UPDATED, mass_player_id
    )
    state = hass.states.get(entity_id)
    assert state
    assert int(float(state.state)) == new_value


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
    # we only have two non read-only player options, bass and treble
    assert sum(1 for entry in registry_entries if entry.domain == NUMBER_DOMAIN) == 2


async def test_name_translation_availability(
    hass: HomeAssistant,
) -> None:
    """Verify available translation keys are in strings.json."""
    # verify, that PLAYER_OPTIONS_TRANSLATION_KEYS_NUMBER matches strings.json
    translations = await async_get_translations(
        hass, language=LOCALE_EN, category="entity", integrations=[DOMAIN]
    )
    prefix = f"component.{DOMAIN}.entity.{Platform.NUMBER.value}."
    for translation_key in PLAYER_OPTIONS_NUMBER:
        assert translations.get(f"{prefix}{translation_key}.name") is not None, (
            f"{translation_key} is missing in strings.json for platform number"
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_queue_playback_speed(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test the playback speed number sets the speed of the player's own queue."""
    music_assistant_client.server_info.schema_version = 101
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "number.test_player_1_playback_speed"
    # nothing whose speed can change is playing
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE

    queue = music_assistant_client.player_queues._queues["00:00:00:00:00:01"]
    queue.current_item = QueueItem(
        queue_id="00:00:00:00:00:01",
        queue_item_id="queue_item_1",
        name="Book 1",
        duration=3600,
        media_item=Audiobook(
            item_id="book_1",
            provider="library",
            name="Book 1",
            provider_mappings=set(),
        ),
    )
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.QUEUE_UPDATED, "00:00:00:00:00:01"
    )
    state = hass.states.get(entity_id)
    assert state
    assert float(state.state) == 1.0

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 1.5},
        blocking=True,
    )
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/set_playback_speed",
        queue_id="00:00:00:00:00:01",
        speed=1.5,
        queue_item_id=None,
        require_schema=101,
    )


async def test_queue_playback_speed_registry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    music_assistant_client: MagicMock,
) -> None:
    """Test the playback speed number is added disabled, also before its queue exists."""
    music_assistant_client.server_info.schema_version = 101
    # the server adds the queue after the player
    with patch(
        "tests.components.music_assistant.common.create_player_queues_from_fixture",
        return_value=[],
    ):
        await setup_integration_from_fixtures(hass, music_assistant_client)
    entry = entity_registry.async_get("number.test_player_1_playback_speed")
    assert entry
    assert entry.unique_id == "00:00:00:00:00:01_queue_playback_speed"
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
