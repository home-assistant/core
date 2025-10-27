"""Tests for the Ollama integration."""

from typing import Any
from unittest.mock import patch

from httpx import ConnectError
import pytest

from homeassistant.components import ollama
from homeassistant.components.ollama.const import DOMAIN
from homeassistant.config_entries import ConfigEntryDisabler, ConfigSubentryData
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er, llm
from homeassistant.helpers.device_registry import DeviceEntryDisabler
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from homeassistant.setup import async_setup_component

from . import TEST_OPTIONS

from tests.common import MockConfigEntry

V1_TEST_USER_DATA = {
    ollama.CONF_URL: "http://localhost:11434",
    ollama.CONF_MODEL: "test_model:latest",
}

V1_TEST_OPTIONS = {
    ollama.CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
    ollama.CONF_MAX_HISTORY: 2,
}

V21_TEST_USER_DATA = V1_TEST_USER_DATA
V21_TEST_OPTIONS = V1_TEST_OPTIONS


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ConnectError(message="Connect error"), "Connect error"),
        (RuntimeError("Runtime error"), "Runtime error"),
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
        "ollama.AsyncClient.list",
        side_effect=side_effect,
    ):
        assert await async_setup_component(hass, ollama.DOMAIN, {})
        await hass.async_block_till_done()
        assert error in caplog.text


async def test_migration_from_v1(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 1."""
    # Create a v1 config entry with conversation options and an entity
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=V1_TEST_USER_DATA,
        options=V1_TEST_OPTIONS,
        version=1,
        title="llama-3.2-8b",
    )
    mock_config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Ollama",
        model="Ollama",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity = entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id="llama_3_2_8b",
    )

    # Run migration
    with patch(
        "homeassistant.components.ollama.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.version == 3
    assert mock_config_entry.minor_version == 3
    # After migration, parent entry should only have URL
    assert mock_config_entry.data == {ollama.CONF_URL: "http://localhost:11434"}
    assert mock_config_entry.options == {}

    assert len(mock_config_entry.subentries) == 2

    subentry = next(
        iter(
            entry
            for entry in mock_config_entry.subentries.values()
            if entry.subentry_type == "conversation"
        )
    )
    assert subentry.unique_id is None
    assert subentry.title == "llama-3.2-8b"
    assert subentry.subentry_type == "conversation"
    # Subentry should now include the model from the original options
    expected_subentry_data = TEST_OPTIONS.copy()
    assert subentry.data == expected_subentry_data

    # Find the AI Task subentry
    ai_task_subentry = next(
        iter(
            entry
            for entry in mock_config_entry.subentries.values()
            if entry.subentry_type == "ai_task_data"
        )
    )
    assert ai_task_subentry.unique_id is None
    assert ai_task_subentry.title == "Ollama AI Task"
    assert ai_task_subentry.subentry_type == "ai_task_data"

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


async def test_migration_from_v1_with_multiple_urls(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 1 with different URLs."""
    # Create two v1 config entries with different URLs
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"url": "http://localhost:11434", "model": "llama3.2:latest"},
        options=V1_TEST_OPTIONS,
        version=1,
        title="Ollama 1",
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={"url": "http://localhost:11435", "model": "llama3.2:latest"},
        options=V1_TEST_OPTIONS,
        version=1,
        title="Ollama 2",
    )
    mock_config_entry_2.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Ollama",
        model="Ollama 1",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id="ollama_1",
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)},
        name=mock_config_entry_2.title,
        manufacturer="Ollama",
        model="Ollama 2",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry_2.entry_id,
        config_entry=mock_config_entry_2,
        device_id=device_2.id,
        suggested_object_id="ollama_2",
    )

    # Run migration
    with patch(
        "homeassistant.components.ollama.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2

    for idx, entry in enumerate(entries):
        assert entry.version == 3
        assert entry.minor_version == 3
        assert not entry.options
        assert len(entry.subentries) == 2

        subentry = next(
            iter(
                subentry
                for subentry in entry.subentries.values()
                if subentry.subentry_type == "conversation"
            )
        )
        assert subentry.subentry_type == "conversation"
        # Subentry should include the model along with the original options
        expected_subentry_data = TEST_OPTIONS.copy()
        expected_subentry_data["model"] = "llama3.2:latest"
        assert subentry.data == expected_subentry_data
        assert subentry.title == f"Ollama {idx + 1}"

        # Find the AI Task subentry
        ai_task_subentry = next(
            iter(
                subentry
                for subentry in entry.subentries.values()
                if subentry.subentry_type == "ai_task_data"
            )
        )
        assert ai_task_subentry.subentry_type == "ai_task_data"
        assert ai_task_subentry.title == "Ollama AI Task"

        dev = device_registry.async_get_device(
            identifiers={(DOMAIN, list(entry.subentries.values())[0].subentry_id)}
        )
        assert dev is not None
        assert dev.config_entries == {entry.entry_id}
        assert dev.config_entries_subentries == {entry.entry_id: {subentry.subentry_id}}


async def test_migration_from_v1_with_same_urls(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 1 with same URLs consolidates entries."""
    # Create two v1 config entries with the same URL
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"url": "http://localhost:11434", "model": "llama3.2:latest"},
        options=V1_TEST_OPTIONS,
        version=1,
        title="Ollama",
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={"url": "http://localhost:11434", "model": "llama3.2:latest"},  # Same URL
        options=V1_TEST_OPTIONS,
        version=1,
        title="Ollama 2",
    )
    mock_config_entry_2.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Ollama",
        model="Ollama",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id="ollama",
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)},
        name=mock_config_entry_2.title,
        manufacturer="Ollama",
        model="Ollama",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry_2.entry_id,
        config_entry=mock_config_entry_2,
        device_id=device_2.id,
        suggested_object_id="ollama_2",
    )

    # Run migration
    with patch(
        "homeassistant.components.ollama.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Should have only one entry left (consolidated)
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    entry = entries[0]
    assert entry.version == 3
    assert entry.minor_version == 3
    assert not entry.options
    # Two conversation subentries from the two original entries and 1 aitask subentry
    assert len(entry.subentries) == 3

    # Check both subentries exist with correct data
    subentries = list(entry.subentries.values())
    titles = [sub.title for sub in subentries]
    assert "Ollama" in titles
    assert "Ollama 2" in titles

    conversation_subentries = [
        subentry for subentry in subentries if subentry.subentry_type == "conversation"
    ]
    assert len(conversation_subentries) == 2
    for subentry in conversation_subentries:
        assert subentry.subentry_type == "conversation"
        # Subentry should include the model along with the original options
        expected_subentry_data = TEST_OPTIONS.copy()
        expected_subentry_data["model"] = "llama3.2:latest"
        assert subentry.data == expected_subentry_data

        # Check devices were migrated correctly
        dev = device_registry.async_get_device(
            identifiers={(DOMAIN, subentry.subentry_id)}
        )
        assert dev is not None
        assert dev.config_entries == {mock_config_entry.entry_id}
        assert dev.config_entries_subentries == {
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
                    "conversation_entity_id": "conversation.ollama_2",
                    "device_disabled_by": None,
                    "entity_disabled_by": None,
                    "device": 1,
                },
                {
                    "conversation_entity_id": "conversation.ollama",
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
                    "conversation_entity_id": "conversation.ollama",
                    "device_disabled_by": None,
                    "entity_disabled_by": None,
                    "device": 0,
                },
                {
                    "conversation_entity_id": "conversation.ollama_2",
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
                    "conversation_entity_id": "conversation.ollama",
                    "device_disabled_by": DeviceEntryDisabler.CONFIG_ENTRY,
                    "entity_disabled_by": RegistryEntryDisabler.CONFIG_ENTRY,
                    "device": 0,
                },
                {
                    "conversation_entity_id": "conversation.ollama_2",
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
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"url": "http://localhost:11434", "model": "llama3.2:latest"},
        options=V1_TEST_OPTIONS,
        version=1,
        title="Ollama",
        disabled_by=config_entry_disabled_by[0],
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={"url": "http://localhost:11434", "model": "llama3.2:latest"},
        options=V1_TEST_OPTIONS,
        version=1,
        title="Ollama 2",
        disabled_by=config_entry_disabled_by[1],
    )
    mock_config_entry_2.add_to_hass(hass)
    mock_config_entries = [mock_config_entry, mock_config_entry_2]

    device_1 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Ollama",
        model="Ollama",
        entry_type=dr.DeviceEntryType.SERVICE,
        disabled_by=device_disabled_by[0],
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device_1.id,
        suggested_object_id="ollama",
        disabled_by=entity_disabled_by[0],
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)},
        name=mock_config_entry_2.title,
        manufacturer="Ollama",
        model="Ollama",
        entry_type=dr.DeviceEntryType.SERVICE,
        disabled_by=device_disabled_by[1],
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry_2.entry_id,
        config_entry=mock_config_entry_2,
        device_id=device_2.id,
        suggested_object_id="ollama_2",
        disabled_by=entity_disabled_by[1],
    )

    devices = [device_1, device_2]

    # Run migration
    with patch(
        "homeassistant.components.ollama.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.disabled_by is merged_config_entry_disabled_by
    assert entry.version == 3
    assert entry.minor_version == 3
    assert not entry.options
    assert entry.title == "Ollama"
    assert len(entry.subentries) == 3
    conversation_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "conversation"
    ]
    assert len(conversation_subentries) == 2
    for subentry in conversation_subentries:
        assert subentry.subentry_type == "conversation"
        assert subentry.data == {"model": "llama3.2:latest", **V1_TEST_OPTIONS}
        assert "Ollama" in subentry.title
    ai_task_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "ai_task_data"
    ]
    assert len(ai_task_subentries) == 1
    assert ai_task_subentries[0].data == {"model": "llama3.2:latest"}
    assert ai_task_subentries[0].title == "Ollama AI Task"

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


async def test_migration_from_v2_1(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 2.1.

    This tests we clean up the broken migration in Home Assistant Core
    2025.7.0b0-2025.7.0b1:
    - Fix device registry (Fixed in Home Assistant Core 2025.7.0b2)
    """
    # Create a v2.1 config entry with 2 subentries, devices and entities
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=V21_TEST_USER_DATA,
        entry_id="mock_entry_id",
        version=2,
        minor_version=1,
        subentries_data=[
            ConfigSubentryData(
                data=V21_TEST_OPTIONS,
                subentry_id="mock_id_1",
                subentry_type="conversation",
                title="Ollama",
                unique_id=None,
            ),
            ConfigSubentryData(
                data=V21_TEST_OPTIONS,
                subentry_id="mock_id_2",
                subentry_type="conversation",
                title="Ollama 2",
                unique_id=None,
            ),
        ],
        title="Ollama",
    )
    mock_config_entry.add_to_hass(hass)

    device_1 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id="mock_id_1",
        identifiers={(DOMAIN, "mock_id_1")},
        name="Ollama",
        manufacturer="Ollama",
        model="Ollama",
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
        suggested_object_id="ollama",
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id="mock_id_2",
        identifiers={(DOMAIN, "mock_id_2")},
        name="Ollama 2",
        manufacturer="Ollama",
        model="Ollama",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        "mock_id_2",
        config_entry=mock_config_entry,
        config_subentry_id="mock_id_2",
        device_id=device_2.id,
        suggested_object_id="ollama_2",
    )

    # Run migration
    with patch(
        "homeassistant.components.ollama.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.version == 3
    assert entry.minor_version == 3
    assert not entry.options
    assert entry.title == "Ollama"
    assert len(entry.subentries) == 3
    conversation_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "conversation"
    ]
    assert len(conversation_subentries) == 2
    for subentry in conversation_subentries:
        assert subentry.subentry_type == "conversation"
        # Since TEST_USER_DATA no longer has a model, subentry data should be TEST_OPTIONS
        assert subentry.data == TEST_OPTIONS
        assert "Ollama" in subentry.title

    subentry = conversation_subentries[0]

    entity = entity_registry.async_get("conversation.ollama")
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

    entity = entity_registry.async_get("conversation.ollama_2")
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


async def test_migration_from_v2_2(hass: HomeAssistant) -> None:
    """Test migration from version 2.2."""
    subentry_data = ConfigSubentryData(
        data=V21_TEST_USER_DATA,
        subentry_type="conversation",
        title="Test Conversation",
        unique_id=None,
    )

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            ollama.CONF_URL: "http://localhost:11434",
            ollama.CONF_MODEL: "test_model:latest",  # Model still in main data
        },
        version=2,
        minor_version=2,
        subentries_data=[subentry_data],
    )
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ollama.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Check migration to v3.1
    assert mock_config_entry.version == 3
    assert mock_config_entry.minor_version == 3

    # Check that model was moved from main data to subentry
    assert mock_config_entry.data == {ollama.CONF_URL: "http://localhost:11434"}
    assert len(mock_config_entry.subentries) == 2

    subentry = next(iter(mock_config_entry.subentries.values()))
    assert subentry.data == {
        **V21_TEST_USER_DATA,
        ollama.CONF_MODEL: "test_model:latest",
    }


async def test_migration_from_v3_1_without_subentry(hass: HomeAssistant) -> None:
    """Test migration from version 3.1 where there is no existing subentry.

    This exercises the code path where the model is not moved to a subentry
    because the subentry does not exist, which is a scenario that can happen
    if the user created the config entry without adding a subentry, or
    if the user manually removed the subentry after the migration to v3.1.
    """
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            ollama.CONF_MODEL: "test_model:latest",
        },
        version=3,
        minor_version=1,
    )
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ollama.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.version == 3
    assert mock_config_entry.minor_version == 3

    assert next(iter(mock_config_entry.subentries.values()), None) is None


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
async def test_migrate_entry_from_v3_2(
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
    """Test migration from version 3.2."""
    # Create a v3.2 config entry with conversation subentries
    conversation_subentry_id = "blabla"
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://localhost:11434"},
        disabled_by=config_entry_disabled_by,
        version=3,
        minor_version=2,
        subentries_data=[
            {
                "data": V1_TEST_OPTIONS,
                "subentry_id": conversation_subentry_id,
                "subentry_type": "conversation",
                "title": "Ollama",
                "unique_id": None,
            },
            {
                "data": {"model": "llama3.2:latest"},
                "subentry_type": "ai_task_data",
                "title": "Ollama AI Task",
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
        manufacturer="Ollama",
        model="Ollama",
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
        suggested_object_id="ollama",
    )

    # Verify initial state
    assert mock_config_entry.version == 3
    assert mock_config_entry.minor_version == 2
    assert len(mock_config_entry.subentries) == 2
    assert mock_config_entry.disabled_by == config_entry_disabled_by
    assert conversation_device.disabled_by == device_disabled_by
    assert conversation_entity.disabled_by == entity_disabled_by

    # Run setup to trigger migration
    with patch(
        "homeassistant.components.ollama.async_setup_entry",
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
    assert entry.version == 3
    assert entry.minor_version == minor_version_after_migration

    # Check the disabled_by flag on config entry, device and entity are as expected
    conversation_device = device_registry.async_get(conversation_device.id)
    conversation_entity = entity_registry.async_get(conversation_entity.entity_id)
    assert mock_config_entry.disabled_by == config_entry_disabled_by_after_migration
    assert conversation_device.disabled_by == device_disabled_by_after_migration
    assert conversation_entity.disabled_by == entity_disabled_by_after_migration
