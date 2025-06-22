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

from homeassistant.components.anthropic.const import DEFAULT_CONVERSATION_NAME, DOMAIN
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
        manufacturer="Claude",
        model="Anthropic",
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

    assert mock_config_entry.version == 2
    assert mock_config_entry.data == {"api_key": "1234"}
    assert mock_config_entry.options == {}

    assert len(mock_config_entry.subentries) == 1

    subentry = next(iter(mock_config_entry.subentries.values()))
    assert subentry.unique_id is None
    assert subentry.title == DEFAULT_CONVERSATION_NAME
    assert subentry.subentry_type == "conversation"
    assert subentry.data == OPTIONS

    migrated_entity = entity_registry.async_get(entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.config_entry_id == mock_config_entry.entry_id
    assert migrated_entity.config_subentry_id == subentry.subentry_id
    assert migrated_entity.device_id == device.id
