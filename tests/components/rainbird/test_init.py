"""Tests for rainbird initialization."""


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


@pytest.mark.parametrize(
    "yaml_config,config_entry_data,responses",
    [
        ({}, CONFIG_ENTRY_DATA, [mock_response(SERIAL_RESPONSE)]),
        (
            CONFIG,
            None,
            [
                mock_response(SERIAL_RESPONSE),  # Issued during import
                mock_response(SERIAL_RESPONSE),
            ],
        ),
    ],
    ids=["config_entry", "yaml"],
)
async def test_init_success(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test successful setup and unload."""

    assert await setup_integration()

    assert [entry.state for entry in hass.config_entries.async_entries(DOMAIN)] == [
        ConfigEntryState.LOADED
    ]


@pytest.mark.parametrize(
    "yaml_config,config_entry_data,responses,config_entry_states",
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
