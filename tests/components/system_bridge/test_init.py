"""Test the System Bridge integration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from systembridgeconnector.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgemodels.fixtures.modules.processes import FIXTURE_PROCESSES
import voluptuous as vol

from homeassistant.components.system_bridge import (
    CONF_BRIDGE,
    CONF_KEY,
    CONF_TEXT,
    SERVICE_GET_PROCESS_BY_ID,
    SERVICE_GET_PROCESSES_BY_NAME,
    SERVICE_OPEN_PATH,
    SERVICE_OPEN_URL,
    SERVICE_POWER_COMMAND,
    SERVICE_SEND_KEYPRESS,
    SERVICE_SEND_TEXT,
)
from homeassistant.components.system_bridge.config_flow import SystemBridgeConfigFlow
from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_COMMAND,
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PATH,
    CONF_PORT,
    CONF_TOKEN,
    CONF_URL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from . import FIXTURE_USER_INPUT, FIXTURE_UUID, setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    assert mock_version.check_supported.call_count == 0

    assert mock_websocket_client.connect.call_count == 0
    assert mock_websocket_client.listen.call_count == 0
    assert mock_websocket_client.close.call_count == 0

    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert mock_version.check_supported.call_count == 1

    assert mock_websocket_client.connect.call_count == 2
    assert mock_websocket_client.listen.call_count == 2

    assert entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_version_authentication_error(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test authentication error from version call."""
    mock_version.check_supported.side_effect = AuthenticationException

    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_version_connection_closed(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test connection closed from version call."""
    mock_version.check_supported.side_effect = ConnectionClosedException

    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_version_connection_error(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test connection error from version call."""
    mock_version.check_supported.side_effect = ConnectionErrorException

    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_version_timeout(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test timeout from version call."""
    mock_version.check_supported.side_effect = asyncio.TimeoutError

    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_version_not_supported(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test version not supported."""
    mock_version.check_supported.return_value = False

    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state == ConfigEntryState.SETUP_RETRY

    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=f"system_bridge_{entry.entry_id}_unsupported_version",
    )


async def test_get_data_authentication_error(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test authentication error from get_data call."""
    mock_websocket_client.get_data.side_effect = AuthenticationException

    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_get_data_connection_closed(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test connection closed from get_data call."""
    mock_websocket_client.get_data.side_effect = ConnectionClosedException

    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_get_data_connection_error(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test connection error from get_data call."""
    mock_websocket_client.get_data.side_effect = ConnectionErrorException

    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_get_data_timeout(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test timeout from get_data call."""
    mock_websocket_client.get_data.side_effect = asyncio.TimeoutError

    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_already_has_services(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if services are registered."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state == ConfigEntryState.LOADED

    assert hass.services.has_service(DOMAIN, SERVICE_GET_PROCESS_BY_ID)
    assert hass.services.has_service(DOMAIN, SERVICE_GET_PROCESSES_BY_NAME)
    assert hass.services.has_service(DOMAIN, SERVICE_OPEN_PATH)
    assert hass.services.has_service(DOMAIN, SERVICE_POWER_COMMAND)
    assert hass.services.has_service(DOMAIN, SERVICE_OPEN_URL)
    assert hass.services.has_service(DOMAIN, SERVICE_SEND_KEYPRESS)
    assert hass.services.has_service(DOMAIN, SERVICE_SEND_TEXT)

    new_config_entry = MockConfigEntry(
        title="Title 2",
        domain=DOMAIN,
        unique_id="uuid2",
        version=SystemBridgeConfigFlow.VERSION,
        minor_version=SystemBridgeConfigFlow.MINOR_VERSION,
        data={
            CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
            CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
            CONF_TOKEN: FIXTURE_USER_INPUT[CONF_TOKEN],
        },
    )
    await setup_integration(hass, new_config_entry)
    entry_2 = hass.config_entries.async_entries(DOMAIN)[1]

    assert entry_2.state == ConfigEntryState.LOADED

    assert hass.services.has_service(DOMAIN, SERVICE_GET_PROCESS_BY_ID)
    assert hass.services.has_service(DOMAIN, SERVICE_GET_PROCESSES_BY_NAME)
    assert hass.services.has_service(DOMAIN, SERVICE_OPEN_PATH)
    assert hass.services.has_service(DOMAIN, SERVICE_POWER_COMMAND)
    assert hass.services.has_service(DOMAIN, SERVICE_OPEN_URL)
    assert hass.services.has_service(DOMAIN, SERVICE_SEND_KEYPRESS)
    assert hass.services.has_service(DOMAIN, SERVICE_SEND_TEXT)


async def test_services(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if services are registered."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state == ConfigEntryState.LOADED

    assert hass.services.has_service(DOMAIN, SERVICE_GET_PROCESS_BY_ID)
    assert hass.services.has_service(DOMAIN, SERVICE_GET_PROCESSES_BY_NAME)
    assert hass.services.has_service(DOMAIN, SERVICE_OPEN_PATH)
    assert hass.services.has_service(DOMAIN, SERVICE_POWER_COMMAND)
    assert hass.services.has_service(DOMAIN, SERVICE_OPEN_URL)
    assert hass.services.has_service(DOMAIN, SERVICE_SEND_KEYPRESS)
    assert hass.services.has_service(DOMAIN, SERVICE_SEND_TEXT)

    # Test invalid device
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PROCESS_BY_ID,
            {
                CONF_BRIDGE: "invalidid",
                CONF_ID: FIXTURE_PROCESSES[0].id,
            },
            blocking=True,
            return_response=True,
        )

    # Get device from device registry
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, FIXTURE_UUID)})
    assert device is not None

    # Test process by id with valid id
    await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PROCESS_BY_ID,
        {
            CONF_BRIDGE: device.id,
            CONF_ID: FIXTURE_PROCESSES[0].id,
        },
        blocking=True,
        return_response=True,
    )

    # Test process by id with invalid id
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PROCESS_BY_ID,
            {
                CONF_BRIDGE: device.id,
                CONF_ID: 999999999,
            },
            blocking=True,
            return_response=True,
        )

    # Test processes by name
    await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PROCESSES_BY_NAME,
        {
            CONF_BRIDGE: device.id,
            CONF_NAME: FIXTURE_PROCESSES[0].name,
        },
        blocking=True,
        return_response=True,
    )

    # Test open path
    await hass.services.async_call(
        DOMAIN,
        SERVICE_OPEN_PATH,
        {
            CONF_BRIDGE: device.id,
            CONF_PATH: "/test/path",
        },
        blocking=True,
        return_response=True,
    )

    # Test power command
    await hass.services.async_call(
        DOMAIN,
        SERVICE_POWER_COMMAND,
        {
            CONF_BRIDGE: device.id,
            CONF_COMMAND: "shutdown",
        },
        blocking=True,
        return_response=True,
    )

    # Test open url
    await hass.services.async_call(
        DOMAIN,
        SERVICE_OPEN_URL,
        {
            CONF_BRIDGE: device.id,
            CONF_URL: "https://www.example.com",
        },
        blocking=True,
        return_response=True,
    )

    # Test send keypress
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_KEYPRESS,
        {
            CONF_BRIDGE: device.id,
            CONF_KEY: "key",
        },
        blocking=True,
        return_response=True,
    )

    # Test send text
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_TEXT,
        {
            CONF_BRIDGE: device.id,
            CONF_TEXT: "text",
        },
        blocking=True,
        return_response=True,
    )


async def test_migration_minor_1_to_2(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UUID,
        data={
            CONF_API_KEY: FIXTURE_USER_INPUT[CONF_TOKEN],
            CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
            CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        },
        version=SystemBridgeConfigFlow.VERSION,
        minor_version=1,
    )

    await setup_integration(hass, config_entry)

    assert len(mock_setup_entry.mock_calls) == 1

    # Check that the version has been updated and the api_key has been moved to token
    assert config_entry.version == SystemBridgeConfigFlow.VERSION
    assert config_entry.minor_version == SystemBridgeConfigFlow.MINOR_VERSION
    assert config_entry.data == {
        CONF_API_KEY: FIXTURE_USER_INPUT[CONF_TOKEN],
        CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
        CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        CONF_TOKEN: FIXTURE_USER_INPUT[CONF_TOKEN],
    }
    assert config_entry.state == ConfigEntryState.LOADED


async def test_migration_minor_future_version(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test migration."""
    config_entry_data = {
        CONF_API_KEY: FIXTURE_USER_INPUT[CONF_TOKEN],
        CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
        CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        CONF_TOKEN: FIXTURE_USER_INPUT[CONF_TOKEN],
    }
    config_entry_version = SystemBridgeConfigFlow.VERSION
    config_entry_minor_version = SystemBridgeConfigFlow.MINOR_VERSION + 1
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UUID,
        data=config_entry_data,
        version=config_entry_version,
        minor_version=config_entry_minor_version,
    )

    await setup_integration(hass, config_entry)

    assert len(mock_setup_entry.mock_calls) == 1

    assert config_entry.version == config_entry_version
    assert config_entry.minor_version == config_entry_minor_version
    assert config_entry.data == config_entry_data
    assert config_entry.state == ConfigEntryState.LOADED
