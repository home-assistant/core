"""Tests for the Anthropic integration."""

from typing import Any
from unittest.mock import patch

from anthropic import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
)
from httpx import URL, Request, Response
import pytest

from homeassistant.components.anthropic.const import DOMAIN
from homeassistant.config_entries import ConfigEntryDisabler, ConfigSubentryData
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryDisabler
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (APIConnectionError(request=None), "Connection error"),
        (APITimeoutError(request=None), "Request timed out"),
        (
            BadRequestError(
                message="Your credit balance is too low to access the Claude API. Please go to Plans & Billing to upgrade or purchase credits.",
                response=Response(
                    status_code=400,
                    request=Request(method="POST", url=URL()),
                ),
                body={"type": "error", "error": {"type": "invalid_request_error"}},
            ),
            "anthropic integration not ready yet: Your credit balance is too low to access the Claude API",
        ),
        (
            AuthenticationError(
                message="invalid x-api-key",
                response=Response(
                    status_code=401,
                    request=Request(method="POST", url=URL()),
                ),
                body={"type": "error", "error": {"type": "authentication_error"}},
            ),
            "Invalid API key",
        ),
    ],
)
async def test_init_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    side_effect,
    error,
) -> None:
    """Test initialization errors."""
    with patch(
        "anthropic.resources.models.AsyncModels.retrieve",
        side_effect=side_effect,
    ):
        assert await async_setup_component(hass, "anthropic", {})
        await hass.async_block_till_done()
        assert error in caplog.text


async def test_migration_from_v1_to_v2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 1 to version 2."""
    # Create a v1 config entry with conversation options and an entity
    OPTIONS = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "claude-3-haiku-20240307",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "1234"},
        options=OPTIONS,
        version=1,
        title="Claude",
    )
    mock_config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity = entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id="claude",
    )

    # Run migration
    with patch(
        "homeassistant.components.anthropic.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.version == 2
    assert mock_config_entry.minor_version == 3
    assert mock_config_entry.data == {"api_key": "1234"}
    assert mock_config_entry.options == {}

    assert len(mock_config_entry.subentries) == 1

    subentry = next(iter(mock_config_entry.subentries.values()))
    assert subentry.unique_id is None
    assert subentry.title == "Claude"
    assert subentry.subentry_type == "conversation"
    assert subentry.data == OPTIONS

    migrated_entity = entity_registry.async_get(entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.config_entry_id == mock_config_entry.entry_id
    assert migrated_entity.config_subentry_id == subentry.subentry_id
    assert migrated_entity.unique_id == subentry.subentry_id

    # Check device migration
    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert (
        migrated_device := device_registry.async_get_device(
            identifiers={(DOMAIN, subentry.subentry_id)}
        )
    )
    assert migrated_device.identifiers == {(DOMAIN, subentry.subentry_id)}
    assert migrated_device.id == device.id
    assert migrated_device.config_entries == {mock_config_entry.entry_id}
    assert migrated_device.config_entries_subentries == {
        mock_config_entry.entry_id: {subentry.subentry_id}
    }


@pytest.mark.parametrize(
    (
        "config_entry_disabled_by",
        "device_disabled_by",
        "entity_disabled_by",
        "merged_config_entry_disabled_by",
        "conversation_subentry_data",
        "main_config_entry",
    ),
    [
        (
            [ConfigEntryDisabler.USER, None],
            [DeviceEntryDisabler.CONFIG_ENTRY, None],
            [RegistryEntryDisabler.CONFIG_ENTRY, None],
            None,
            [
                {
                    "conversation_entity_id": "conversation.claude_2",
                    "device_disabled_by": None,
                    "entity_disabled_by": None,
                    "device": 1,
                },
                {
                    "conversation_entity_id": "conversation.claude",
                    "device_disabled_by": DeviceEntryDisabler.USER,
                    "entity_disabled_by": RegistryEntryDisabler.DEVICE,
                    "device": 0,
                },
            ],
            1,
        ),
        (
            [None, ConfigEntryDisabler.USER],
            [None, DeviceEntryDisabler.CONFIG_ENTRY],
            [None, RegistryEntryDisabler.CONFIG_ENTRY],
            None,
            [
                {
                    "conversation_entity_id": "conversation.claude",
                    "device_disabled_by": None,
                    "entity_disabled_by": None,
                    "device": 0,
                },
                {
                    "conversation_entity_id": "conversation.claude_2",
                    "device_disabled_by": DeviceEntryDisabler.USER,
                    "entity_disabled_by": RegistryEntryDisabler.DEVICE,
                    "device": 1,
                },
            ],
            0,
        ),
        (
            [ConfigEntryDisabler.USER, ConfigEntryDisabler.USER],
            [DeviceEntryDisabler.CONFIG_ENTRY, DeviceEntryDisabler.CONFIG_ENTRY],
            [RegistryEntryDisabler.CONFIG_ENTRY, RegistryEntryDisabler.CONFIG_ENTRY],
            ConfigEntryDisabler.USER,
            [
                {
                    "conversation_entity_id": "conversation.claude",
                    "device_disabled_by": DeviceEntryDisabler.CONFIG_ENTRY,
                    "entity_disabled_by": RegistryEntryDisabler.CONFIG_ENTRY,
                    "device": 0,
                },
                {
                    "conversation_entity_id": "conversation.claude_2",
                    "device_disabled_by": DeviceEntryDisabler.CONFIG_ENTRY,
                    "entity_disabled_by": RegistryEntryDisabler.CONFIG_ENTRY,
                    "device": 1,
                },
            ],
            0,
        ),
    ],
)
async def test_migration_from_v1_disabled(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_disabled_by: list[ConfigEntryDisabler | None],
    device_disabled_by: list[DeviceEntryDisabler | None],
    entity_disabled_by: list[RegistryEntryDisabler | None],
    merged_config_entry_disabled_by: ConfigEntryDisabler | None,
    conversation_subentry_data: list[dict[str, Any]],
    main_config_entry: int,
) -> None:
    """Test migration where the config entries are disabled."""
    # Create a v1 config entry with conversation options and an entity
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "claude-3-haiku-20240307",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "1234"},
        options=options,
        version=1,
        title="Claude",
        disabled_by=config_entry_disabled_by[0],
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "1234"},
        options=options,
        version=1,
        title="Claude 2",
        disabled_by=config_entry_disabled_by[1],
    )
    mock_config_entry_2.add_to_hass(hass)
    mock_config_entries = [mock_config_entry, mock_config_entry_2]

    device_1 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
        disabled_by=device_disabled_by[0],
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device_1.id,
        suggested_object_id="claude",
        disabled_by=entity_disabled_by[0],
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)},
        name=mock_config_entry_2.title,
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
        disabled_by=device_disabled_by[1],
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry_2.entry_id,
        config_entry=mock_config_entry_2,
        device_id=device_2.id,
        suggested_object_id="claude",
        disabled_by=entity_disabled_by[1],
    )

    devices = [device_1, device_2]

    # Run migration
    with patch(
        "homeassistant.components.anthropic.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.disabled_by is merged_config_entry_disabled_by
    assert entry.version == 2
    assert entry.minor_version == 3
    assert not entry.options
    assert entry.title == "Claude conversation"
    assert len(entry.subentries) == 2
    conversation_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "conversation"
    ]
    assert len(conversation_subentries) == 2
    for subentry in conversation_subentries:
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options
        assert "Claude" in subentry.title

    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)}
    )

    for idx, subentry in enumerate(conversation_subentries):
        subentry_data = conversation_subentry_data[idx]
        entity = entity_registry.async_get(subentry_data["conversation_entity_id"])
        assert entity.unique_id == subentry.subentry_id
        assert entity.config_subentry_id == subentry.subentry_id
        assert entity.config_entry_id == entry.entry_id
        assert entity.disabled_by is subentry_data["entity_disabled_by"]

        assert (
            device := device_registry.async_get_device(
                identifiers={(DOMAIN, subentry.subentry_id)}
            )
        )
        assert device.identifiers == {(DOMAIN, subentry.subentry_id)}
        assert device.id == devices[subentry_data["device"]].id
        assert device.config_entries == {
            mock_config_entries[main_config_entry].entry_id
        }
        assert device.config_entries_subentries == {
            mock_config_entries[main_config_entry].entry_id: {subentry.subentry_id}
        }
        assert device.disabled_by is subentry_data["device_disabled_by"]


async def test_migration_from_v1_to_v2_with_multiple_keys(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 1 to version 2 with different API keys."""
    # Create two v1 config entries with different API keys
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "claude-3-haiku-20240307",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "1234"},
        options=options,
        version=1,
        title="Claude 1",
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "12345"},
        options=options,
        version=1,
        title="Claude 2",
    )
    mock_config_entry_2.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Anthropic",
        model="Claude 1",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id="claude_1",
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)},
        name=mock_config_entry_2.title,
        manufacturer="Anthropic",
        model="Claude 2",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry_2.entry_id,
        config_entry=mock_config_entry_2,
        device_id=device_2.id,
        suggested_object_id="claude_2",
    )

    # Run migration
    with patch(
        "homeassistant.components.anthropic.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2

    for idx, entry in enumerate(entries):
        assert entry.version == 2
        assert entry.minor_version == 3
        assert not entry.options
        assert len(entry.subentries) == 1
        subentry = list(entry.subentries.values())[0]
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options
        assert subentry.title == f"Claude {idx + 1}"

        dev = device_registry.async_get_device(
            identifiers={(DOMAIN, list(entry.subentries.values())[0].subentry_id)}
        )
        assert dev is not None
        assert dev.config_entries == {entry.entry_id}
        assert dev.config_entries_subentries == {entry.entry_id: {subentry.subentry_id}}


async def test_migration_from_v1_to_v2_with_same_keys(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 1 to version 2 with same API keys consolidates entries."""
    # Create two v1 config entries with the same API key
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "claude-3-haiku-20240307",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "1234"},
        options=options,
        version=1,
        title="Claude",
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "1234"},  # Same API key
        options=options,
        version=1,
        title="Claude 2",
    )
    mock_config_entry_2.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id="claude",
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)},
        name=mock_config_entry_2.title,
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry_2.entry_id,
        config_entry=mock_config_entry_2,
        device_id=device_2.id,
        suggested_object_id="claude_2",
    )

    # Run migration
    with patch(
        "homeassistant.components.anthropic.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Should have only one entry left (consolidated)
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    entry = entries[0]
    assert entry.version == 2
    assert entry.minor_version == 3
    assert not entry.options
    assert len(entry.subentries) == 2  # Two subentries from the two original entries

    # Check both subentries exist with correct data
    subentries = list(entry.subentries.values())
    titles = [sub.title for sub in subentries]
    assert "Claude" in titles
    assert "Claude 2" in titles

    for subentry in subentries:
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options

        # Check devices were migrated correctly
        dev = device_registry.async_get_device(
            identifiers={(DOMAIN, subentry.subentry_id)}
        )
        assert dev is not None
        assert dev.config_entries == {mock_config_entry.entry_id}
        assert dev.config_entries_subentries == {
            mock_config_entry.entry_id: {subentry.subentry_id}
        }


async def test_migration_from_v2_1_to_v2_2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 2.1 to version 2.2.

    This tests we clean up the broken migration in Home Assistant Core
    2025.7.0b0-2025.7.0b1:
    - Fix device registry (Fixed in Home Assistant Core 2025.7.0b2)
    """
    # Create a v2.1 config entry with 2 subentries, devices and entities
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "claude-3-haiku-20240307",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "1234"},
        entry_id="mock_entry_id",
        version=2,
        minor_version=1,
        subentries_data=[
            ConfigSubentryData(
                data=options,
                subentry_id="mock_id_1",
                subentry_type="conversation",
                title="Claude",
                unique_id=None,
            ),
            ConfigSubentryData(
                data=options,
                subentry_id="mock_id_2",
                subentry_type="conversation",
                title="Claude 2",
                unique_id=None,
            ),
        ],
        title="Claude",
    )
    mock_config_entry.add_to_hass(hass)

    device_1 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id="mock_id_1",
        identifiers={(DOMAIN, "mock_id_1")},
        name="Claude",
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    device_1 = device_registry.async_update_device(
        device_1.id, add_config_entry_id="mock_entry_id", add_config_subentry_id=None
    )
    assert device_1.config_entries_subentries == {"mock_entry_id": {None, "mock_id_1"}}
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        "mock_id_1",
        config_entry=mock_config_entry,
        config_subentry_id="mock_id_1",
        device_id=device_1.id,
        suggested_object_id="claude",
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id="mock_id_2",
        identifiers={(DOMAIN, "mock_id_2")},
        name="Claude 2",
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        "mock_id_2",
        config_entry=mock_config_entry,
        config_subentry_id="mock_id_2",
        device_id=device_2.id,
        suggested_object_id="claude_2",
    )

    # Run migration
    with patch(
        "homeassistant.components.anthropic.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.version == 2
    assert entry.minor_version == 3
    assert not entry.options
    assert entry.title == "Claude"
    assert len(entry.subentries) == 2
    conversation_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "conversation"
    ]
    assert len(conversation_subentries) == 2
    for subentry in conversation_subentries:
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options
        assert "Claude" in subentry.title

    subentry = conversation_subentries[0]

    entity = entity_registry.async_get("conversation.claude")
    assert entity.unique_id == subentry.subentry_id
    assert entity.config_subentry_id == subentry.subentry_id
    assert entity.config_entry_id == entry.entry_id

    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert (
        device := device_registry.async_get_device(
            identifiers={(DOMAIN, subentry.subentry_id)}
        )
    )
    assert device.identifiers == {(DOMAIN, subentry.subentry_id)}
    assert device.id == device_1.id
    assert device.config_entries == {mock_config_entry.entry_id}
    assert device.config_entries_subentries == {
        mock_config_entry.entry_id: {subentry.subentry_id}
    }

    subentry = conversation_subentries[1]

    entity = entity_registry.async_get("conversation.claude_2")
    assert entity.unique_id == subentry.subentry_id
    assert entity.config_subentry_id == subentry.subentry_id
    assert entity.config_entry_id == entry.entry_id
    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert (
        device := device_registry.async_get_device(
            identifiers={(DOMAIN, subentry.subentry_id)}
        )
    )
    assert device.identifiers == {(DOMAIN, subentry.subentry_id)}
    assert device.id == device_2.id
    assert device.config_entries == {mock_config_entry.entry_id}
    assert device.config_entries_subentries == {
        mock_config_entry.entry_id: {subentry.subentry_id}
    }


@pytest.mark.parametrize(
    (
        "config_entry_disabled_by",
        "device_disabled_by",
        "entity_disabled_by",
        "setup_result",
        "minor_version_after_migration",
        "config_entry_disabled_by_after_migration",
        "device_disabled_by_after_migration",
        "entity_disabled_by_after_migration",
    ),
    [
        # Config entry not disabled, update device and entity disabled by config entry
        (
            None,
            DeviceEntryDisabler.CONFIG_ENTRY,
            RegistryEntryDisabler.CONFIG_ENTRY,
            True,
            3,
            None,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.DEVICE,
        ),
        (
            None,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.DEVICE,
            True,
            3,
            None,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.DEVICE,
        ),
        (
            None,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.USER,
            True,
            3,
            None,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.USER,
        ),
        (
            None,
            None,
            None,
            True,
            3,
            None,
            None,
            None,
        ),
        # Config entry disabled, migration does not run
        (
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.CONFIG_ENTRY,
            RegistryEntryDisabler.CONFIG_ENTRY,
            False,
            2,
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.CONFIG_ENTRY,
            RegistryEntryDisabler.CONFIG_ENTRY,
        ),
        (
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.DEVICE,
            False,
            2,
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.DEVICE,
        ),
        (
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.USER,
            False,
            2,
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.USER,
        ),
        (
            ConfigEntryDisabler.USER,
            None,
            None,
            False,
            2,
            ConfigEntryDisabler.USER,
            None,
            None,
        ),
    ],
)
async def test_migrate_entry_to_v2_3(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_disabled_by: ConfigEntryDisabler | None,
    device_disabled_by: DeviceEntryDisabler | None,
    entity_disabled_by: RegistryEntryDisabler | None,
    setup_result: bool,
    minor_version_after_migration: int,
    config_entry_disabled_by_after_migration: ConfigEntryDisabler | None,
    device_disabled_by_after_migration: ConfigEntryDisabler | None,
    entity_disabled_by_after_migration: RegistryEntryDisabler | None,
) -> None:
    """Test migration to version 2.3."""
    # Create a v2.2 config entry with conversation subentries
    conversation_subentry_id = "blabla"
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        disabled_by=config_entry_disabled_by,
        version=2,
        minor_version=2,
        subentries_data=[
            {
                "data": {
                    "recommended": True,
                    "llm_hass_api": ["assist"],
                    "prompt": "You are a helpful assistant",
                    "chat_model": "claude-3-haiku-20240307",
                },
                "subentry_id": conversation_subentry_id,
                "subentry_type": "conversation",
                "title": "Claude haiku",
                "unique_id": None,
            },
        ],
    )
    mock_config_entry.add_to_hass(hass)

    conversation_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id=conversation_subentry_id,
        disabled_by=device_disabled_by,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    conversation_entity = entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        config_subentry_id=conversation_subentry_id,
        disabled_by=entity_disabled_by,
        device_id=conversation_device.id,
        suggested_object_id="claude",
    )

    # Verify initial state
    assert mock_config_entry.version == 2
    assert mock_config_entry.minor_version == 2
    assert len(mock_config_entry.subentries) == 1
    assert mock_config_entry.disabled_by == config_entry_disabled_by
    assert conversation_device.disabled_by == device_disabled_by
    assert conversation_entity.disabled_by == entity_disabled_by

    # Run setup to trigger migration
    with patch(
        "homeassistant.components.anthropic.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert result is setup_result
        await hass.async_block_till_done()

    # Verify migration completed
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]

    # Check version and subversion were updated
    assert entry.version == 2
    assert entry.minor_version == minor_version_after_migration

    # Check the disabled_by flag on config entry, device and entity are as expected
    conversation_device = device_registry.async_get(conversation_device.id)
    conversation_entity = entity_registry.async_get(conversation_entity.entity_id)
    assert mock_config_entry.disabled_by == config_entry_disabled_by_after_migration
    assert conversation_device.disabled_by == device_disabled_by_after_migration
    assert conversation_entity.disabled_by == entity_disabled_by_after_migration
