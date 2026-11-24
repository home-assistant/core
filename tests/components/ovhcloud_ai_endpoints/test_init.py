"""Tests for the OVHcloud AI Endpoints integration setup."""

import subprocess
import sys
from unittest.mock import AsyncMock

import httpx2
from openai import AuthenticationError, BadRequestError, OpenAIError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ovhcloud_ai_endpoints.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_MODEL, CONF_PROMPT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

IMPORT_TIMEOUT = 60


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
                response=httpx2.Response(
                    status_code=401,
                    request=httpx2.Request(method="POST", url="https://example.com"),
                ),
                body=None,
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            BadRequestError(
                message="invalid parameter",
                response=httpx2.Response(
                    status_code=400,
                    request=httpx2.Request(method="POST", url="https://example.com"),
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

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, subentry.subentry_id), entry.entry_id
    )
    assert device is not None
    assert device.name == "Meta-Llama-3_3-70B-Instruct"


CHECK_CLIENT_RESOURCE_IMPORTS = """
import importlib

import homeassistant.components.ovhcloud_ai_endpoints
import openai

imports = []
import_module = importlib.import_module


def record_import(name, package=None):
    imports.append(name)
    return import_module(name, package)


importlib.import_module = record_import
client = openai.AsyncOpenAI(api_key="test")
client.chat.completions
print(imports)
"""


def test_client_resources_are_imported_with_the_integration() -> None:
    """Accessing the client chat resource must not import anything in the event loop.

    The OpenAI client imports its chat resource on first use through
    importlib.import_module, which Home Assistant reports as a blocking call
    when it happens in the event loop. Having the submodules in sys.modules is
    not enough: the call uses a relative name that the check does not resolve.

    A clean interpreter is the only way to see this: anything the test suite
    imported first would hide it.
    """
    result = subprocess.run(
        [sys.executable, "-c", CHECK_CLIENT_RESOURCE_IMPORTS],
        capture_output=True,
        check=True,
        text=True,
        timeout=IMPORT_TIMEOUT,
    )

    assert result.stdout.strip() == "[]"
