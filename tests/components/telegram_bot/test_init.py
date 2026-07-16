"""Init tests for the Telegram Bot integration."""

import pytest

from homeassistant.components.telegram_bot.const import (
    ATTR_PARSER,
    CONF_ALLOWED_CHAT_IDS,
    CONF_API_ENDPOINT,
    CONF_CHAT_ID,
    DEFAULT_API_ENDPOINT,
    DOMAIN,
    PARSER_MD,
    PLATFORM_BROADCAST,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_migration_error(
    hass: HomeAssistant,
    mock_external_calls: None,
) -> None:
    """Test migrate config entry from unsupported version."""

    mock_config_entry = MockConfigEntry(
        unique_id="mock api key",
        domain=DOMAIN,
        data={
            CONF_PLATFORM: PLATFORM_BROADCAST,
            CONF_API_KEY: "mock api key",
        },
        options={ATTR_PARSER: PARSER_MD},
        version=99,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_migrate_entry_from_1_1(
    hass: HomeAssistant,
    mock_external_calls: None,
) -> None:
    """Test migrate config entry from 1.1, chaining through to the latest version."""

    mock_config_entry = MockConfigEntry(
        unique_id="mock api key",
        domain=DOMAIN,
        data={
            CONF_PLATFORM: PLATFORM_BROADCAST,
            CONF_API_KEY: "mock api key",
        },
        options={ATTR_PARSER: PARSER_MD},
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 3
    assert mock_config_entry.data == {
        CONF_PLATFORM: PLATFORM_BROADCAST,
        CONF_API_KEY: "mock api key",
        CONF_API_ENDPOINT: DEFAULT_API_ENDPOINT,
    }


@pytest.mark.parametrize(
    "chats_without_notify_entity",
    [
        pytest.param((), id="notify entities intact"),
        pytest.param((654321,), id="notify entity deleted"),
    ],
)
async def test_migrate_entry_to_per_chat_devices(
    hass: HomeAssistant,
    mock_external_calls: None,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    chats_without_notify_entity: tuple[int, ...],
) -> None:
    """Test migrating chats sharing one bot device to per-chat devices.

    On this device-registry model a device may belong to multiple subentries, so the shared
    bot device holds the event entity (subentry None) and every chat's notify entity across
    subentries. The migration must move each chat's notify entity onto its own per-chat
    device (linked to the bot device) and leave the bot device associated with only
    (entry, None), so the future device-registry redesign keeps it at None.

    A chat's notify entity may have been deleted while the bot device keeps that chat's
    subentry association, so the migration must strip the association either way.
    """
    bot_id = 123456  # test_user id from mock_external_calls
    chat_ids = (123456, 654321)
    config_entry = MockConfigEntry(
        unique_id="mock api key",
        domain=DOMAIN,
        minor_version=2,
        data={
            CONF_PLATFORM: PLATFORM_BROADCAST,
            CONF_API_KEY: "mock api key",
            CONF_API_ENDPOINT: DEFAULT_API_ENDPOINT,
        },
        options={ATTR_PARSER: PARSER_MD},
        subentries_data=[
            ConfigSubentryData(
                unique_id="123456",
                data={CONF_CHAT_ID: 123456},
                subentry_type=CONF_ALLOWED_CHAT_IDS,
                title="chat 1",
            ),
            ConfigSubentryData(
                unique_id="654321",
                data={CONF_CHAT_ID: 654321},
                subentry_type=CONF_ALLOWED_CHAT_IDS,
                title="chat 2",
            ),
        ],
    )
    config_entry.add_to_hass(hass)
    subentry_ids = list(config_entry.subentries)

    # Pre-migration state: one shared bot device associated with the config entry (None)
    # and every chat subentry, holding the event entity and every chat's notify entity.
    bot_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, str(bot_id))},
    )
    for subentry_id in subentry_ids:
        bot_device = device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            config_subentry_id=subentry_id,
            identifiers={(DOMAIN, str(bot_id))},
        )
    assert bot_device.config_entries_subentries == {
        config_entry.entry_id: {None, *subentry_ids}
    }

    event_entity = entity_registry.async_get_or_create(
        "event",
        DOMAIN,
        f"{bot_id}_update_event",
        config_entry=config_entry,
        device_id=bot_device.id,
    )
    notify_entities = {
        chat_id: entity_registry.async_get_or_create(
            "notify",
            DOMAIN,
            f"{bot_id}_{chat_id}",
            config_entry=config_entry,
            config_subentry_id=subentry_id,
            device_id=bot_device.id,
        )
        for subentry_id, chat_id in zip(subentry_ids, chat_ids, strict=True)
        if chat_id not in chats_without_notify_entity
    }

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.minor_version == 3

    # Each chat has its own device, owned by that chat's subentry and linked to the bot
    # device.
    chat_devices = {
        chat_id: device_registry.async_get_device(
            identifiers={(DOMAIN, f"{bot_id}_{chat_id}")}
        )
        for chat_id in chat_ids
    }
    for subentry_id, chat_id in zip(subentry_ids, chat_ids, strict=True):
        chat_device = chat_devices[chat_id]
        assert chat_device is not None
        assert chat_device.config_entries_subentries == {
            config_entry.entry_id: {subentry_id}
        }
        assert chat_device.via_device_id == bot_device.id

    # Every notify entity that survived is moved onto its chat's device
    for chat_id, notify_entity in notify_entities.items():
        assert (
            entity_registry.async_get(notify_entity.entity_id).device_id
            == chat_devices[chat_id].id
        )

    # The bot device ends up associated with only (entry, None), keeping the event entity
    bot_device = device_registry.async_get(bot_device.id)
    assert bot_device is not None
    assert bot_device.config_entries_subentries == {config_entry.entry_id: {None}}
    assert entity_registry.async_get(event_entity.entity_id).device_id == bot_device.id


async def test_per_chat_devices(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Each chat gets its own device linked to the config-entry-level bot device."""
    mock_broadcast_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    entry_id = mock_broadcast_config_entry.entry_id

    # The bot device belongs to the config entry (no subentry) and holds the event entity
    bot_device = device_registry.async_get_device(identifiers={(DOMAIN, "123456")})
    assert bot_device is not None
    assert bot_device.config_entries_subentries == {entry_id: {None}}
    assert bot_device.name == "Mock Title"

    for chat_id, chat_name in ((123456, "mock chat 1"), (654321, "mock chat 2")):
        subentry_id = next(
            sid
            for sid, subentry in mock_broadcast_config_entry.subentries.items()
            if subentry.data[CONF_CHAT_ID] == chat_id
        )
        chat_device = device_registry.async_get_device(
            identifiers={(DOMAIN, f"123456_{chat_id}")}
        )
        assert chat_device is not None
        assert chat_device.config_entries_subentries == {entry_id: {subentry_id}}
        assert chat_device.via_device_id == bot_device.id
        # The device is named after the chat, and its notify entity takes the device name
        assert chat_device.name == chat_name
        notify_entity_id = entity_registry.async_get_entity_id(
            "notify", DOMAIN, f"123456_{chat_id}"
        )
        assert notify_entity_id is not None
        assert entity_registry.async_get(notify_entity_id).device_id == chat_device.id
        assert hass.states.get(notify_entity_id).name == chat_name


async def test_remove_chat_subentry_removes_per_chat_device(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Removing a chat subentry removes just its per-chat device and notify entity."""
    mock_broadcast_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    subentry_id = next(
        sid
        for sid, subentry in mock_broadcast_config_entry.subentries.items()
        if subentry.data[CONF_CHAT_ID] == 123456
    )
    assert device_registry.async_get_device(identifiers={(DOMAIN, "123456_123456")})
    assert entity_registry.async_get_entity_id("notify", DOMAIN, "123456_123456")

    hass.config_entries.async_remove_subentry(mock_broadcast_config_entry, subentry_id)
    await hass.async_block_till_done()

    # The removed chat's device and notify entity are gone; the other chat and the bot
    # device remain
    assert not device_registry.async_get_device(identifiers={(DOMAIN, "123456_123456")})
    assert not entity_registry.async_get_entity_id("notify", DOMAIN, "123456_123456")
    assert device_registry.async_get_device(identifiers={(DOMAIN, "123456_654321")})
    assert device_registry.async_get_device(identifiers={(DOMAIN, "123456")})
