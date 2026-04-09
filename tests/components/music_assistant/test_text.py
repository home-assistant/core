"""Test Music Assistant text entities."""

from unittest.mock import MagicMock, call

from music_assistant_models.enums import EventType
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.music_assistant.const import DOMAIN
from homeassistant.components.music_assistant.text import (
    PLAYER_OPTIONS_TRANSLATION_KEYS_TEXT,
)
from homeassistant.components.text import (
    ATTR_VALUE,
    DOMAIN as TEXT_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import LOCALE_EN, async_get_translations

from .common import (
    setup_integration_from_fixtures,
    snapshot_music_assistant_entities,
    trigger_subscription_callback,
)


async def test_text_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    music_assistant_client: MagicMock,
) -> None:
    """Test text entities."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    snapshot_music_assistant_entities(hass, entity_registry, snapshot, Platform.TEXT)


async def test_text_set_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test text set action."""
    mass_player_id = "00:00:00:00:00:01"
    mass_option_key = "network_name"
    entity_id = "text.test_player_1_network_name"

    option_value = "new name"

    await setup_integration_from_fixtures(hass, music_assistant_client)
    state = hass.states.get(entity_id)
    assert state

    await hass.services.async_call(
        TEXT_DOMAIN,
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


async def test_external_update(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test external value update."""
    mass_player_id = "00:00:00:00:00:01"
    mass_option_key = "network_name"
    entity_id = "text.test_player_1_network_name"

    await setup_integration_from_fixtures(hass, music_assistant_client)

    # get current option and remove it
    text_option = next(
        option
        for option in music_assistant_client.players._players[mass_player_id].options
        if option.key == mass_option_key
    )
    music_assistant_client.players._players[mass_player_id].options.remove(text_option)

    # set new value different from previous one
    previous_value = text_option.value
    new_value = "other name"
    text_option.value = new_value
    assert previous_value != text_option.value
    music_assistant_client.players._players[mass_player_id].options.append(text_option)

    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PLAYER_OPTIONS_UPDATED, mass_player_id
    )
    state = hass.states.get(entity_id)
    assert state
    assert state.state == new_value


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
    # we only have a single non read-only player option
    assert sum(1 for entry in registry_entries if entry.domain == TEXT_DOMAIN) == 1


async def test_name_translation_availability(
    hass: HomeAssistant,
) -> None:
    """Verify, that the list of available translation keys is reflected in strings.json."""
    # verify, that PLAYER_OPTIONS_TRANSLATION_KEYS_text matches strings.json
    translations = await async_get_translations(
        hass, language=LOCALE_EN, category="entity", integrations=[DOMAIN]
    )
    prefix = f"component.{DOMAIN}.entity.{Platform.TEXT.value}."
    for translation_key in PLAYER_OPTIONS_TRANSLATION_KEYS_TEXT:
        assert translations.get(f"{prefix}{translation_key}.name") is not None, (
            f"{translation_key} is missing in strings.json for platform text"
        )
