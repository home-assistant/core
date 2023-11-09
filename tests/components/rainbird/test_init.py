"""Tests for rainbird initialization."""

from __future__ import annotations

from http import HTTPStatus

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import (
    CONFIG_ENTRY_DATA,
    MODEL_AND_VERSION_RESPONSE,
    mock_response,
    mock_response_error,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMockResponse


@pytest.mark.parametrize(
    ("config_entry_data", "initial_response"),
    [
        (CONFIG_ENTRY_DATA, None),
    ],
    ids=["config_entry"],
)
async def test_init_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    responses: list[AiohttpClientMockResponse],
    initial_response: AiohttpClientMockResponse | None,
) -> None:
    """Test successful setup and unload."""
    if initial_response:
        responses.insert(0, initial_response)

    await config_entry.async_setup(hass)
    assert config_entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("config_entry_data", "responses", "config_entry_state"),
    [
        (
            CONFIG_ENTRY_DATA,
            [mock_response_error(HTTPStatus.SERVICE_UNAVAILABLE)],
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            CONFIG_ENTRY_DATA,
            [mock_response_error(HTTPStatus.INTERNAL_SERVER_ERROR)],
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            CONFIG_ENTRY_DATA,
            [
                mock_response(MODEL_AND_VERSION_RESPONSE),
                mock_response_error(HTTPStatus.SERVICE_UNAVAILABLE),
            ],
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            CONFIG_ENTRY_DATA,
            [
                mock_response(MODEL_AND_VERSION_RESPONSE),
                mock_response_error(HTTPStatus.INTERNAL_SERVER_ERROR),
            ],
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=[
        "unavailable",
        "server-error",
        "coordinator-unavailable",
        "coordinator-server-error",
    ],
)
async def test_communication_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_entry_state: list[ConfigEntryState],
) -> None:
    """Test unable to talk to device on startup, which fails setup."""

    await config_entry.async_setup(hass)
    assert config_entry.state == config_entry_state
