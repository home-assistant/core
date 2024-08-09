"""Tests for the SwitchBot Cloud integration services."""

from unittest.mock import patch

import pytest
from switchbot_api import Device

from homeassistant.components.switchbot_cloud import (
    SwitchBotAPI,
    make_list_devices,
    make_send_command_service,
)
from homeassistant.core import ServiceCall


@pytest.fixture
def mock_list_devices():
    """Mock list_devices."""
    with patch.object(SwitchBotAPI, "list_devices") as mock_list_devices:
        yield mock_list_devices


@pytest.fixture
def mock_send_command():
    """Mock send_command."""
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        yield mock_send_command


async def test_make_list_devices(mock_list_devices):
    """Test make_list_devices."""
    unique_id = "test-id"
    device_name = "test-name"
    device_type = "Plug"
    expected_devices = [
        Device(
            deviceId=unique_id,
            deviceName=device_name,
            deviceType=device_type,
            hubDeviceId="test-hub-id",
        )
    ]
    mock_list_devices.return_value = expected_devices
    api = SwitchBotAPI("test-token", "test-secret")
    list_devices = make_list_devices(api)
    assert list_devices is not None
    devices = await list_devices(None)
    assert devices == {
        "items": [
            {
                "unique_id": unique_id,
                "device_name": device_name,
                "device_type": device_type,
            }
        ]
    }


async def test_make_send_command_service(mock_send_command):
    """Test make_send_command_service."""
    unique_id = "test-id"
    command_type = "test-command-type"
    command = "test-command"
    parameter = "test-parameter"
    api = SwitchBotAPI("test-token", "test-secret")
    send_command_service = make_send_command_service(api)
    assert send_command_service is not None
    await send_command_service(
        ServiceCall(
            domain="switchbot_cloud",
            service="send_command",
            data={
                "unique_id": unique_id,
                "command_type": command_type,
                "command": command,
                "parameter": parameter,
            },
        )
    )
    mock_send_command.assert_called_once_with(
        unique_id, command, command_type, parameter
    )
