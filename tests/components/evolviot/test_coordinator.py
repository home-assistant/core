"""Test the EvolvIOT coordinator."""

from unittest.mock import AsyncMock, patch

from pyevolviot import EvolvIOTApiError, EvolvIOTCommandResult, EvolvIOTConnectionError
import pytest

from homeassistant.components.evolviot.coordinator import EvolvIOTDataUpdateCoordinator
from homeassistant.core import HomeAssistant

from .conftest import MockEvolvIOTWebSocket

from tests.common import MockConfigEntry

ACCEPTED_COMMAND_RESULT = EvolvIOTCommandResult.from_payload(
    {
        "entity_id": "switch.evolviot_switch",
        "command": {"accepted": True, "acked": True},
        "state": {
            "entity_id": "switch.evolviot_switch",
            "available": True,
            "state": "on",
        },
    }
)
REJECTED_COMMAND_RESULT = EvolvIOTCommandResult.from_payload(
    {
        "entity_id": "switch.evolviot_switch",
        "command": {"accepted": False, "acked": False},
    }
)


async def test_command_falls_back_when_websocket_disconnected(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_websocket: MockEvolvIOTWebSocket,
) -> None:
    """Test commands use HTTP during a WebSocket reconnect."""
    coordinator: EvolvIOTDataUpdateCoordinator = setup_integration.runtime_data
    mock_websocket.closed = True

    with patch.object(
        coordinator.api,
        "async_send_command",
        AsyncMock(return_value=ACCEPTED_COMMAND_RESULT),
    ) as mock_send_command:
        await coordinator.async_command("switch.evolviot_switch", "turn_on")

    mock_send_command.assert_awaited_once_with("switch.evolviot_switch", "turn_on")
    assert coordinator.states["switch.evolviot_switch"].is_on


async def test_command_falls_back_when_websocket_disconnects_during_dispatch(
    setup_integration: MockConfigEntry,
    mock_websocket: MockEvolvIOTWebSocket,
) -> None:
    """Test commands fall back to HTTP when dispatch races a disconnect."""
    coordinator: EvolvIOTDataUpdateCoordinator = setup_integration.runtime_data

    with (
        patch.object(
            mock_websocket,
            "async_command",
            AsyncMock(side_effect=EvolvIOTConnectionError),
        ) as mock_websocket_command,
        patch.object(
            coordinator.api,
            "async_send_command",
            AsyncMock(return_value=ACCEPTED_COMMAND_RESULT),
        ) as mock_send_command,
    ):
        await coordinator.async_command("switch.evolviot_switch", "turn_on")

    mock_websocket_command.assert_awaited_once_with("switch.evolviot_switch", "turn_on")
    mock_send_command.assert_awaited_once_with("switch.evolviot_switch", "turn_on")
    assert coordinator.states["switch.evolviot_switch"].is_on


async def test_rejected_websocket_command_raises(
    setup_integration: MockConfigEntry,
    mock_websocket: MockEvolvIOTWebSocket,
) -> None:
    """Test a rejected WebSocket command raises an API error."""
    coordinator: EvolvIOTDataUpdateCoordinator = setup_integration.runtime_data

    with (
        patch.object(
            mock_websocket,
            "async_command",
            AsyncMock(return_value=REJECTED_COMMAND_RESULT),
        ),
        pytest.raises(EvolvIOTApiError, match="rejected"),
    ):
        await coordinator.async_command("switch.evolviot_switch", "turn_on")


async def test_rejected_http_command_raises(
    setup_integration: MockConfigEntry,
    mock_websocket: MockEvolvIOTWebSocket,
) -> None:
    """Test a rejected HTTP fallback command raises an API error."""
    coordinator: EvolvIOTDataUpdateCoordinator = setup_integration.runtime_data
    mock_websocket.closed = True

    with (
        patch.object(
            coordinator.api,
            "async_send_command",
            AsyncMock(return_value=REJECTED_COMMAND_RESULT),
        ),
        pytest.raises(EvolvIOTApiError, match="rejected"),
    ):
        await coordinator.async_command("switch.evolviot_switch", "turn_on")
