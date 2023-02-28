"""Tests for rainbird initialization."""

from __future__ import annotations

import pytest

from homeassistant.components.rainbird import DOMAIN
from homeassistant.components.rainbird.const import ATTR_CONFIG_ENTRY_ID, ATTR_DURATION
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .conftest import (
    ACK_ECHO,
    CONFIG,
    CONFIG_ENTRY_DATA,
    SERIAL_NUMBER,
    SERIAL_RESPONSE,
    UNAVAILABLE_RESPONSE,
    ComponentSetup,
    mock_response,
)

from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


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


@pytest.mark.parametrize("platforms", [[Platform.NUMBER, Platform.SENSOR]])
async def test_rain_delay_service(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    responses: list[str],
    config_entry: ConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test calling the rain delay service."""

    assert await setup_integration()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, SERIAL_NUMBER)})
    assert device
    assert device.name == "Rain Bird Controller"

    aioclient_mock.mock_calls.clear()
    responses.append(mock_response(ACK_ECHO))

    await hass.services.async_call(
        DOMAIN,
        "set_rain_delay",
        {ATTR_CONFIG_ENTRY_ID: config_entry.entry_id, ATTR_DURATION: 3},
        blocking=True,
    )

    assert len(aioclient_mock.mock_calls) == 1

    issue = issue_registry.async_get_issue(
        domain=DOMAIN, issue_id="deprecated_raindelay"
    )
    assert issue
    assert issue.translation_placeholders == {
        "alternate_target": "number.rain_bird_controller_rain_delay"
    }


async def test_rain_delay_invalid_config_entry(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    config_entry: ConfigEntry,
) -> None:
    """Test calling the rain delay service."""

    assert await setup_integration()

    aioclient_mock.mock_calls.clear()

    with pytest.raises(HomeAssistantError, match="Config entry id does not exist"):
        await hass.services.async_call(
            DOMAIN,
            "set_rain_delay",
            {ATTR_CONFIG_ENTRY_ID: "invalid", ATTR_DURATION: 3},
            blocking=True,
        )

    assert len(aioclient_mock.mock_calls) == 0
