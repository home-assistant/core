"""Test the EvolvIOT coordinator."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.evolviot.coordinator import (
    EvolvIOTDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

from .conftest import MockEvolvIOTWebSocket


async def test_command_falls_back_when_websocket_disconnected(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_websocket: MockEvolvIOTWebSocket,
) -> None:
    """Test commands use HTTP during a WebSocket reconnect."""
    coordinator: EvolvIOTDataUpdateCoordinator = setup_integration.runtime_data
    mock_websocket.closed = True

    with patch.object(
        coordinator.api, "async_send_command", AsyncMock()
    ) as mock_send_command:
        await coordinator.async_command("switch.evolviot_switch", "turn_on")

    mock_send_command.assert_awaited_once_with(
        "switch.evolviot_switch", "turn_on"
    )
