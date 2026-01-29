"""Test System Bridge services."""

from unittest.mock import MagicMock

import pytest
from systembridgeconnector.exceptions import (
    BadRequestException,
    ConnectionErrorException,
)
from systembridgeconnector.models.command_result import ExecuteResult
from systembridgeconnector.models.response import Response
from systembridgeconnector.models.settings import (
    SettingsCommandDefinition,
    SettingsCommands,
)

from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.components.system_bridge.services import (
    CONF_BRIDGE,
    CONF_COMMAND_ID,
    CONF_KEY,
    CONF_TEXT,
    SERVICE_EXECUTE_COMMAND,
    SERVICE_GET_COMMANDS,
    SERVICE_GET_PROCESS_BY_ID,
    SERVICE_GET_PROCESSES_BY_NAME,
    SERVICE_OPEN_PATH,
    SERVICE_OPEN_URL,
    SERVICE_POWER_COMMAND,
    SERVICE_SEND_KEYPRESS,
    SERVICE_SEND_TEXT,
)
from homeassistant.const import CONF_COMMAND, CONF_ID, CONF_NAME, CONF_PATH, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import FIXTURE_UUID

from tests.common import MockConfigEntry


async def test_service_get_process_by_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_websocket_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test get_process_by_id service."""
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FIXTURE_UUID)}
    )
    assert device_entry

    # Get a valid process ID from the fixture
    processes = mock_websocket_client.get_data.return_value.processes
    valid_process_id = processes[0].id

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PROCESS_BY_ID,
        {CONF_BRIDGE: device_entry.id, CONF_ID: valid_process_id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert response["id"] == valid_process_id


async def test_service_get_process_by_id_not_found(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_websocket_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test get_process_by_id service with non-existent process."""
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FIXTURE_UUID)}
    )
    assert device_entry

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PROCESS_BY_ID,
            {CONF_BRIDGE: device_entry.id, CONF_ID: 999999},
            blocking=True,
            return_response=True,
        )


async def test_service_get_processes_by_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_websocket_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test get_processes_by_name service."""
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FIXTURE_UUID)}
    )
    assert device_entry

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PROCESSES_BY_NAME,
        {CONF_BRIDGE: device_entry.id, CONF_NAME: "python"},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert "count" in response
    assert "processes" in response


async def test_service_get_commands(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_websocket_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test get_commands service."""
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FIXTURE_UUID)}
    )
    assert device_entry

    mock_websocket_client.get_commands.return_value = SettingsCommands(
        allowlist=[
            SettingsCommandDefinition(
                id="test-cmd",
                name="Test Command",
                command="echo hello",
                workingDir="/home/testuser",
                arguments=[],
            )
        ]
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_COMMANDS,
        {CONF_BRIDGE: device_entry.id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert response["count"] == 1
    assert len(response["commands"]) == 1
    mock_websocket_client.get_commands.assert_called_once()


async def test_service_get_commands_connection_error(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_websocket_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test get_commands service with connection error."""
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FIXTURE_UUID)}
    )
    assert device_entry

    mock_websocket_client.get_commands.side_effect = ConnectionErrorException(
        "Connection failed"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_COMMANDS,
            {CONF_BRIDGE: device_entry.id},
            blocking=True,
            return_response=True,
        )


async def test_service_open_path(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_websocket_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test open_path service."""
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FIXTURE_UUID)}
    )
    assert device_entry

    mock_websocket_client.open_path.return_value = Response(
        id="test", type="open_path", data={}, message="Opened"
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_OPEN_PATH,
        {CONF_BRIDGE: device_entry.id, CONF_PATH: "/home/user/documents"},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    mock_websocket_client.open_path.assert_called_once()


async def test_service_open_url(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_websocket_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test open_url service."""
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FIXTURE_UUID)}
    )
    assert device_entry

    mock_websocket_client.open_url.return_value = Response(
        id="test", type="open_url", data={}, message="Opened"
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_OPEN_URL,
        {CONF_BRIDGE: device_entry.id, CONF_URL: "https://example.com"},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    mock_websocket_client.open_url.assert_called_once()


async def test_service_send_keypress(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_websocket_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test send_keypress service."""
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FIXTURE_UUID)}
    )
    assert device_entry

    mock_websocket_client.keyboard_keypress.return_value = Response(
        id="test", type="keyboard_keypress", data={}, message="Key pressed"
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_KEYPRESS,
        {CONF_BRIDGE: device_entry.id, CONF_KEY: "enter"},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    mock_websocket_client.keyboard_keypress.assert_called_once()


async def test_service_send_text(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_websocket_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test send_text service."""
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FIXTURE_UUID)}
    )
    assert device_entry

    mock_websocket_client.keyboard_text.return_value = Response(
        id="test", type="keyboard_text", data={}, message="Text sent"
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_TEXT,
        {CONF_BRIDGE: device_entry.id, CONF_TEXT: "Hello World"},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    mock_websocket_client.keyboard_text.assert_called_once()


async def test_service_power_command(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_websocket_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test power_command service."""
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FIXTURE_UUID)}
    )
    assert device_entry

    mock_websocket_client.power_sleep.return_value = Response(
        id="test", type="power_sleep", data={}, message="Sleep initiated"
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_POWER_COMMAND,
        {CONF_BRIDGE: device_entry.id, CONF_COMMAND: "sleep"},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    mock_websocket_client.power_sleep.assert_called_once()


async def test_service_execute_command(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_websocket_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test execute_command service."""
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FIXTURE_UUID)}
    )
    assert device_entry

    mock_websocket_client.execute_command.return_value = ExecuteResult(
        commandID="test-cmd",
        exitCode=0,
        stdout="output",
        stderr="",
        error=None,
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_EXECUTE_COMMAND,
        {CONF_BRIDGE: device_entry.id, CONF_COMMAND_ID: "test-cmd"},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert response["exitCode"] == 0
    mock_websocket_client.execute_command.assert_called_once()


async def test_service_execute_command_not_found(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_websocket_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test execute_command service with command not found."""
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FIXTURE_UUID)}
    )
    assert device_entry

    mock_websocket_client.execute_command.side_effect = BadRequestException(
        "COMMAND_NOT_FOUND"
    )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_EXECUTE_COMMAND,
            {CONF_BRIDGE: device_entry.id, CONF_COMMAND_ID: "nonexistent"},
            blocking=True,
            return_response=True,
        )


async def test_service_execute_command_timeout(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_websocket_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test execute_command service with timeout."""
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FIXTURE_UUID)}
    )
    assert device_entry

    mock_websocket_client.execute_command.side_effect = ConnectionErrorException(
        "TIMEOUT"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_EXECUTE_COMMAND,
            {CONF_BRIDGE: device_entry.id, CONF_COMMAND_ID: "test-cmd"},
            blocking=True,
            return_response=True,
        )


async def test_service_execute_command_connection_error(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_websocket_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test execute_command service with connection error."""
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FIXTURE_UUID)}
    )
    assert device_entry

    mock_websocket_client.execute_command.side_effect = ConnectionErrorException(
        "Connection failed"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_EXECUTE_COMMAND,
            {CONF_BRIDGE: device_entry.id, CONF_COMMAND_ID: "test-cmd"},
            blocking=True,
            return_response=True,
        )


async def test_service_bad_device_id(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test service with bad device ID."""
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_OPEN_URL,
            {CONF_BRIDGE: "bad-device-id", CONF_URL: "https://example.com"},
            blocking=True,
            return_response=True,
        )


async def test_service_non_system_bridge_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_websocket_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test service with a device that is not a system_bridge device."""
    other_domain = "other_integration"
    other_config_id = "other_config_entry"
    other_mock_config_entry = MockConfigEntry(
        title="Other Integration", domain=other_domain, entry_id=other_config_id
    )
    other_mock_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=other_config_id,
        identifiers={(other_domain, "other-device")},
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_OPEN_URL,
            {CONF_BRIDGE: device_entry.id, CONF_URL: "https://example.com"},
            blocking=True,
            return_response=True,
        )
