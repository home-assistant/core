"""Tests for rainbird initialization."""


import pytest

from homeassistant.components.rainbird import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .conftest import (
    ACK_ECHO,
    CONFIG,
    CONFIG_ENTRY_DATA,
    RAIN_DELAY,
    SERIAL_NUMBER,
    SERIAL_RESPONSE,
    UNAVAILABLE_RESPONSE,
    ComponentSetup,
    mock_response,
)

from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


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
        (
            CONFIG,
            CONFIG_ENTRY_DATA,
            [mock_response(SERIAL_RESPONSE), mock_response(SERIAL_RESPONSE)],
        ),
    ],
    ids=["config_entry", "yaml", "already_exists"],
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


@pytest.mark.parametrize("platforms", [[Platform.SENSOR]])
async def test_rain_delay_service(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
    config_entry: ConfigEntry,
) -> None:
    """Test calling the rain delay service."""

    responses.append(mock_response(RAIN_DELAY))
    assert await setup_integration()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, SERIAL_NUMBER)})
    assert device
    assert device.name == "Rain Bird"

    aioclient_mock.mock_calls.clear()
    responses.extend(
        [
            mock_response(ACK_ECHO),
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        "set_rain_delay",
        {ATTR_DEVICE_ID: device.id, "duration": 30},
        blocking=True,
    )

    assert len(aioclient_mock.mock_calls) == 1


async def test_rain_delay_invalid_device(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
    config_entry: ConfigEntry,
) -> None:
    """Test calling the rain delay service."""

    assert await setup_integration()

    aioclient_mock.mock_calls.clear()
    responses.extend(
        [
            mock_response(ACK_ECHO),
        ]
    )

    with pytest.raises(HomeAssistantError, match="Device id did not match"):
        await hass.services.async_call(
            DOMAIN,
            "set_rain_delay",
            {ATTR_DEVICE_ID: "invalid-device-id", "duration": 30},
            blocking=True,
        )

    assert len(aioclient_mock.mock_calls) == 0
