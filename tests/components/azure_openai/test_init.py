"""Tests for the Azure OpenAI integration."""

from unittest.mock import AsyncMock, patch

import httpx
from openai import APIConnectionError, AuthenticationError, BadRequestError
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.azure_openai.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(
            APIConnectionError(request=httpx.Request(method="GET", url="test")),
            id="connection",
        ),
        pytest.param(
            BadRequestError(
                response=httpx.Response(
                    status_code=500, request=httpx.Request(method="GET", url="test")
                ),
                body=None,
                message="",
            ),
            id="api",
        ),
    ],
)
async def test_init_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    side_effect: APIConnectionError | BadRequestError,
) -> None:
    """Test initialization errors."""
    with patch(
        "openai.resources.models.AsyncModels.list",
        new_callable=AsyncMock,
        side_effect=side_effect,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
        assert mock_config_entry.error_reason_translation_key == "cannot_connect"


async def test_init_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test auth error during init errors."""
    with patch(
        "openai.resources.models.AsyncModels.list",
        new_callable=AsyncMock,
        side_effect=AuthenticationError(
            response=httpx.Response(
                status_code=500, request=httpx.Request(method="GET", url="test")
            ),
            body=None,
            message="",
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
        assert mock_config_entry.error_reason_translation_key == "authentication_failed"


async def test_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test devices are correctly created for subentries."""
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices) == 4

    # Concurrent platform setup makes device ordering nondeterministic.
    conversation_subentry = next(
        subentry
        for subentry in mock_config_entry.subentries.values()
        if subentry.subentry_type == "conversation"
    )
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, conversation_subentry.subentry_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert device == snapshot(exclude=props("identifiers"))


async def test_remove_subentry_removes_device_and_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removing a subentry removes its service device and entity."""
    conversation_subentry = next(
        subentry
        for subentry in mock_config_entry.subentries.values()
        if subentry.subentry_type == "conversation"
    )
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, conversation_subentry.subentry_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert entity_registry.async_get("conversation.azure_openai_conversation")

    assert hass.config_entries.async_remove_subentry(
        mock_config_entry, conversation_subentry.subentry_id
    )
    await hass.async_block_till_done()

    assert device_registry.async_get(device.id) is None
    assert entity_registry.async_get("conversation.azure_openai_conversation") is None
