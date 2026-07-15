"""Fixtures for EvolvIOT tests."""

import asyncio
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, patch

from pyevolviot import (
    EvolvIOTCommandResult,
    EvolvIOTData,
    EvolvIOTEvent,
    EvolvIOTState,
    EvolvIOTStateChangedEvent,
)
import pytest

from homeassistant.components.evolviot.const import (
    CONF_ACCESS_TOKEN,
    CONF_API_BASE_URL,
    CONF_REFRESH_TOKEN,
    CONF_VERIFY_SSL,
    DEFAULT_API_BASE_URL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTITY_ID = "switch.evolviot_switch"
UNIQUE_ID = "SWITCH123/power"


def evolviot_data(state: str = "off") -> EvolvIOTData:
    """Return typed EvolvIOT data."""
    return EvolvIOTData.from_payload(
        {
            "user_id": "user-123",
            "entities": [
                {
                    "entity_id": ENTITY_ID,
                    "unique_id": UNIQUE_ID,
                    "domain": "switch",
                    "name": "Living Room Switch",
                    "device": {
                        "id": "SWITCH123",
                        "name": "Living Room",
                        "manufacturer": "EvolvIOT",
                        "model": "Switch",
                    },
                    "control": {"key": "power"},
                }
            ],
            "states": [
                {
                    "entity_id": ENTITY_ID,
                    "available": True,
                    "state": state,
                    "raw_value": 1 if state == "on" else 0,
                }
            ],
        }
    )


class MockEvolvIOTWebSocket:
    """Mock pyevolviot WebSocket client."""

    def __init__(self, data: EvolvIOTData) -> None:
        """Initialize the mock."""
        self.data = data
        self.commands: list[tuple[str, str]] = []
        self.closed = False
        self._close_event = asyncio.Event()
        self._listeners: list[Callable[[EvolvIOTEvent], Any]] = []

    def async_add_listener(
        self, callback: Callable[[EvolvIOTEvent], Any]
    ) -> Callable[[], None]:
        """Add a WebSocket listener."""
        self._listeners.append(callback)

        def unsubscribe() -> None:
            self._listeners.remove(callback)

        return unsubscribe

    async def async_run_forever(self) -> None:
        """Wait until the mock is closed."""
        await self._close_event.wait()

    async def async_close(self) -> None:
        """Close the mock WebSocket."""
        self.closed = True
        self._close_event.set()

    async def async_refresh(self) -> EvolvIOTData:
        """Return current data."""
        return self.data

    async def async_command(
        self, entity_id: str, command: str
    ) -> EvolvIOTCommandResult:
        """Record a command and emit the resulting state."""
        self.commands.append((entity_id, command))
        state = "on" if command == "turn_on" else "off"
        await self.emit_state(state)
        return EvolvIOTCommandResult.from_payload(
            {
                "entity_id": entity_id,
                "command": {"accepted": True, "acked": True},
                "state": {
                    "entity_id": entity_id,
                    "available": True,
                    "state": state,
                },
            }
        )

    async def emit_state(self, state: str) -> None:
        """Emit a state_changed event."""
        typed_state = EvolvIOTState.from_payload(
            {
                "entity_id": ENTITY_ID,
                "available": True,
                "state": state,
                "raw_value": 1 if state == "on" else 0,
            }
        )
        self.data = self.data.with_state(typed_state)
        await self._emit(EvolvIOTStateChangedEvent(typed_state))

    async def _emit(self, event: EvolvIOTEvent) -> None:
        """Emit an event to listeners."""
        for listener in list(self._listeners):
            result = listener(event)
            if result is not None:
                await result


@pytest.fixture
def mock_websocket() -> MockEvolvIOTWebSocket:
    """Return a mock EvolvIOT WebSocket."""
    return MockEvolvIOTWebSocket(evolviot_data())


@pytest.fixture
def mock_connect_websocket(mock_websocket: MockEvolvIOTWebSocket):
    """Mock the pyevolviot WebSocket connection."""
    with patch(
        "pyevolviot.EvolvIOTApi.async_connect_websocket",
        AsyncMock(return_value=mock_websocket),
    ) as mock_connect:
        yield mock_connect


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_BASE_URL: DEFAULT_API_BASE_URL,
            CONF_ACCESS_TOKEN: "mock-access-token",
            CONF_REFRESH_TOKEN: "mock-refresh-token",
            CONF_VERIFY_SSL: True,
        },
        unique_id="user-123",
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_websocket: AsyncMock,
) -> MockConfigEntry:
    """Set up the EvolvIOT integration."""
    assert mock_connect_websocket is not None
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
