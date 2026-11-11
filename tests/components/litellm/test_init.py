"""Tests for the LiteLLM integration setup."""

import subprocess
import sys
from unittest.mock import AsyncMock

import httpx2
from openai import APIConnectionError, AuthenticationError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

IMPORT_TIMEOUT = 60


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (
            AuthenticationError(
                response=httpx2.Response(
                    status_code=401, request=httpx2.Request("GET", "http://localhost")
                ),
                body=None,
                message="invalid api key",
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (APIConnectionError(request=None), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_error(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test that setup handles errors validating the connection."""
    mock_openai_client.with_options.return_value.models.list.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


def test_client_resources_are_imported_with_the_integration() -> None:
    """Importing the integration must leave no lazy client import for the loop.

    The OpenAI client imports its chat and audio resources on first use, which
    is a conversation turn or a speech-to-text request in the event loop.

    A clean interpreter is the only way to see this: anything the test suite
    imported first would hide it.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, homeassistant.components.litellm; "
            "print(all(m in sys.modules for m in "
            "('openai.resources.chat.chat', 'openai.resources.audio.audio')))",
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=IMPORT_TIMEOUT,
    )

    assert result.stdout.strip() == "True"
