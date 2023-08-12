"""Tests for rainbird initialization."""

from __future__ import annotations

from http import HTTPStatus

import pytest

from homeassistant.components.rainbird import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import CONFIG_ENTRY_DATA, ComponentSetup, mock_response_error

from tests.test_util.aiohttp import AiohttpClientMockResponse


@pytest.mark.parametrize(
    ("yaml_config", "config_entry_data", "initial_response"),
    [
        ({}, CONFIG_ENTRY_DATA, None),
    ],
    ids=["config_entry"],
)
async def test_init_success(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    responses: list[AiohttpClientMockResponse],
    initial_response: AiohttpClientMockResponse | None,
) -> None:
    """Test successful setup and unload."""
    if initial_response:
        responses.insert(0, initial_response)

    assert await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    assert entries[0].state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("yaml_config", "config_entry_data", "responses", "config_entry_states"),
    [
        (
            {},
            CONFIG_ENTRY_DATA,
            [mock_response_error(HTTPStatus.SERVICE_UNAVAILABLE)],
            [ConfigEntryState.SETUP_RETRY],
        ),
        # Note: This should be improved to support reauth when the password is incorrect
        (
            {},
            CONFIG_ENTRY_DATA,
            [mock_response_error(HTTPStatus.FORBIDDEN)],
            [ConfigEntryState.SETUP_RETRY],
        ),
        (
            {},
            CONFIG_ENTRY_DATA,
            [mock_response_error(HTTPStatus.INTERNAL_SERVER_ERROR)],
            [ConfigEntryState.SETUP_RETRY],
        ),
    ],
    ids=["unavailable", "forbidden", "server_error"],
)
async def test_communication_failure(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry_states: list[ConfigEntryState],
) -> None:
    """Test unable to talk to device on startup, which fails setup."""

    assert await setup_integration()

    assert [
        entry.state for entry in hass.config_entries.async_entries(DOMAIN)
    ] == config_entry_states
