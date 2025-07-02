"""Tests for the Ollama integration."""

from unittest.mock import patch

from httpx import ConnectError
import pytest

from homeassistant.components import ollama
from homeassistant.components.ollama.const import DOMAIN
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er, llm
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

    assert mock_config_entry.version == 3
    assert mock_config_entry.minor_version == 1
    # After migration, parent entry should only have URL
    assert mock_config_entry.data == {ollama.CONF_URL: "http://localhost:11434"}
    assert mock_config_entry.options == {}

    assert len(mock_config_entry.subentries) == 1

    subentry = next(iter(mock_config_entry.subentries.values()))
    assert subentry.unique_id is None
    assert subentry.title == "llama-3.2-8b"
    assert subentry.subentry_type == "conversation"
    # Subentry should now include the model from the original options
    expected_subentry_data = TEST_OPTIONS.copy()
    assert subentry.data == expected_subentry_data

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
        assert entry.minor_version == 1
        assert not entry.options
        assert len(entry.subentries) == 1
        subentry = list(entry.subentries.values())[0]
        assert subentry.subentry_type == "conversation"
        # Subentry should include the model along with the original options
        expected_subentry_data = TEST_OPTIONS.copy()
        expected_subentry_data["model"] = "llama3.2:latest"
        assert subentry.data == expected_subentry_data
        assert subentry.title == f"Ollama {idx + 1}"

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
    assert entry.minor_version == 1
    assert not entry.options
    assert len(entry.subentries) == 2  # Two subentries from the two original entries

    # Check both subentries exist with correct data
    subentries = list(entry.subentries.values())
    titles = [sub.title for sub in subentries]
    assert "Ollama" in titles
    assert "Ollama 2" in titles

    for subentry in subentries:
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
    assert entry.minor_version == 1
    assert not entry.options
    assert entry.title == "Ollama"
    assert len(entry.subentries) == 2
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
    assert mock_config_entry.minor_version == 1

    # Check that model was moved from main data to subentry
    assert mock_config_entry.data == {ollama.CONF_URL: "http://localhost:11434"}
    assert len(mock_config_entry.subentries) == 1

    subentry = next(iter(mock_config_entry.subentries.values()))
    assert subentry.data == {
        **V21_TEST_USER_DATA,
        ollama.CONF_MODEL: "test_model:latest",
    }
