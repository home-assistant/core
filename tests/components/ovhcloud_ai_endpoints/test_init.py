"""Tests for the OVHcloud AI Endpoints integration setup."""

from unittest.mock import AsyncMock

import httpx
from openai import AuthenticationError, BadRequestError, OpenAIError
import pytest

from homeassistant.components.ovhcloud_ai_endpoints.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_MODEL, CONF_PROMPT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_unload(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the integration is set up and torn down cleanly."""
    await setup_integration(hass, mock_config_entry, mock_openai_client)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (
            AuthenticationError(
                message="invalid key",
                response=httpx.Response(
                    status_code=401,
                    request=httpx.Request(method="POST", url="https://example.com"),
                ),
                body=None,
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            BadRequestError(
                message="invalid parameter",
                response=httpx.Response(
                    status_code=400,
                    request=httpx.Request(method="POST", url="https://example.com"),
                ),
                body=None,
            ),
            ConfigEntryState.LOADED,
        ),
        (OpenAIError("boom"), ConfigEntryState.SETUP_RETRY),
        (Exception("boom"), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Assert appropriate behavior according to various HTTP responses."""
    mock_openai_client.chat.completions.create.side_effect = exception

    await setup_integration(hass, mock_config_entry, mock_openai_client)
    assert mock_config_entry.state is state


async def test_new_subentry_creates_entity_and_device(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A subentry added after setup must spawn its conversation entity and device."""
    entry = MockConfigEntry(
        title="OVHcloud AI Endpoints",
        domain=DOMAIN,
        data={CONF_API_KEY: "bla"},
    )
    await setup_integration(hass, entry, mock_openai_client)
    assert entry.state is ConfigEntryState.LOADED
    assert not er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    subentry = ConfigSubentry(
        data={
            CONF_MODEL: "Meta-Llama-3_3-70B-Instruct",
            CONF_PROMPT: "You are a helpful assistant.",
        },
        subentry_type="conversation",
        title="Meta-Llama-3_3-70B-Instruct",
        unique_id=None,
    )
    assert hass.config_entries.async_add_subentry(entry, subentry) is True
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == 1
    assert entities[0].domain == "conversation"
    assert entities[0].unique_id == subentry.subentry_id

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, subentry.subentry_id)}
    )
    assert device is not None
    assert device.name == "Meta-Llama-3_3-70B-Instruct"
