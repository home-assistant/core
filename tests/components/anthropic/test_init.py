"""Tests for the Anthropic integration."""

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
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
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
    assert mock_config_entry.minor_version == 2
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
        assert entry.minor_version == 2
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
    assert entry.minor_version == 2
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
    assert entry.minor_version == 2
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
