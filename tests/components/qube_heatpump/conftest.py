"""Common fixtures for the Qube Heat Pump tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.qube_heatpump.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_hub(request: pytest.FixtureRequest) -> Generator[MagicMock]:
    """Mock the Qube Heat Pump hub."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeHub", autospec=True
    ) as mock_hub:

        def create_mock_hub(*args, **kwargs):
            client = MagicMock()
            client.host = args[1] if len(args) > 1 else "1.2.3.4"
            client.port = args[2] if len(args) > 2 else 502
            client.unit = args[4] if len(args) > 4 else 1
            client.label = args[5] if len(args) > 5 else "qube1"
            client.resolved_ip = client.host
            client.entities = []

            # Helper to create awaitable responses
            def create_mock_response(registers=None, bits=None):
                resp = MagicMock()
                resp.isError.return_value = False
                resp.registers = registers or [0] * 50
                resp.bits = bits or [False] * 50
                return resp

            # Ensure all methods that coordinator or setup might call are AsyncMocks
            client.async_connect = AsyncMock(return_value=True)
            client.async_close = AsyncMock(return_value=None)
            client.async_resolve_ip = AsyncMock(return_value=None)
            client.async_read_value = AsyncMock(return_value=1.23)

            # Modbus low level methods
            client.read_holding_registers = AsyncMock(
                side_effect=lambda *args, **kwargs: create_mock_response()
            )
            client.read_input_registers = AsyncMock(
                side_effect=lambda *args, **kwargs: create_mock_response()
            )
            client.read_discrete_inputs = AsyncMock(
                side_effect=lambda *args, **kwargs: create_mock_response(
                    bits=[False] * 50
                )
            )
            client.read_coils = AsyncMock(
                side_effect=lambda *args, **kwargs: create_mock_response(
                    bits=[False] * 50
                )
            )

            client.set_translations = MagicMock()
            return client

        mock_hub.side_effect = create_mock_hub
        yield mock_hub


@pytest.fixture(autouse=True)
def mock_modbus_client():
    """Globally block real Modbus client creation to prevent SocketBlockedError."""
    with patch(
        "python_qube_heatpump.client.AsyncModbusTcpClient",
    ) as mock_client:
        mock_client.return_value.connect = AsyncMock(return_value=True)
        mock_client.return_value.close = MagicMock()
        mock_client.return_value.connected = True
        yield mock_client
