"""Tests for the Ollama integration."""

from unittest.mock import patch

from httpx import ConnectError
import pytest

from homeassistant.components import ollama
from homeassistant.components.ollama.const import DEFAULT_CONVERSATION_NAME, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import TEST_OPTIONS, TEST_USER_DATA

from tests.common import MockConfigEntry


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


async def test_migration_from_v1_to_v2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 1 to version 2."""
    # Create a v1 config entry with conversation options and an entity
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_USER_DATA,
        options=TEST_OPTIONS,
        version=1,
        title="llama-3.2-8b",
    )
    mock_config_entry.add_to_hass(hass)

    entity = entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        suggested_object_id="llama_3_2_8b",
    )

    # Run migration
    with patch(
        "homeassistant.components.ollama.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.version == 2
    assert mock_config_entry.data == TEST_USER_DATA
    assert mock_config_entry.options == {}

    assert len(mock_config_entry.subentries) == 1

    subentry = next(iter(mock_config_entry.subentries.values()))
    assert subentry.unique_id is None
    assert subentry.title == DEFAULT_CONVERSATION_NAME
    assert subentry.subentry_type == "conversation"
    assert subentry.data == TEST_OPTIONS

    migrated_entity = entity_registry.async_get(entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.config_entry_id == mock_config_entry.entry_id
    assert migrated_entity.config_subentry_id == subentry.subentry_id
