"""Tests for rainbird initialization."""

from __future__ import annotations

import pytest

from homeassistant.components.rainbird import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import (
    CONFIG,
    CONFIG_ENTRY_DATA,
    SERIAL_RESPONSE,
    UNAVAILABLE_RESPONSE,
    ComponentSetup,
    mock_response,
)

from tests.test_util.aiohttp import AiohttpClientMockResponse


@pytest.mark.parametrize(
    ("yaml_config", "config_entry_data", "initial_response"),
    [
        ({}, CONFIG_ENTRY_DATA, None),
        (
            CONFIG,
            None,
            mock_response(SERIAL_RESPONSE),  # Extra import request
        ),
        (
            CONFIG,
            CONFIG_ENTRY_DATA,
            None,
        ),
    ],
    ids=["config_entry", "yaml", "already_exists"],
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
        ({}, CONFIG_ENTRY_DATA, [UNAVAILABLE_RESPONSE], [ConfigEntryState.SETUP_RETRY]),
        (
            CONFIG,
            None,
            [
                UNAVAILABLE_RESPONSE,  # Failure when importing yaml
            ],
            [],
        ),
        (
            CONFIG,
            None,
            [
                mock_response(SERIAL_RESPONSE),  # Import succeeds
                UNAVAILABLE_RESPONSE,  # Failure on integration setup
            ],
            [ConfigEntryState.SETUP_RETRY],
        ),
    ],
    ids=["config_entry_failure", "yaml_import_failure", "yaml_init_failure"],
)
async def test_communication_failure(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry_states: list[ConfigEntryState],
) -> None:
    """Test unable to talk to server on startup, which permanently fails setup."""

    assert await setup_integration()

    assert [
        entry.state for entry in hass.config_entries.async_entries(DOMAIN)
    ] == config_entry_states
