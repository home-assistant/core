"""Common fixtures for the Flow-it tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from flow_it_api.models import MachineStatusResponse
import pytest


def get_mock_vmc(
    info_hostname: str = "Flow-it Device",
    state_name: str = "00:11:22:33:44:55",
) -> AsyncMock:
    """Return a mock FlowItVMCMachine."""
    mock_vmc = AsyncMock()
    mock_vmc.get_info.return_value.hostname = info_hostname

    # Load a minimal valid MachineStatusResponse for the fan tests
    mock_vmc.state = MachineStatusResponse(
        lastUpdate=123456789,
        chrono_id="test",
        status=True,
        name=state_name,
        data={
            "event": "update",
            "sensors": {
                "Sin": {"pressure": 1.0, "temperature": 293.15, "humidity": 50.0},
                "Sout": {"pressure": 1.0, "temperature": 293.15, "humidity": 50.0},
                "Iin": {"pressure": 1.0, "temperature": 293.15, "humidity": 50.0},
                "Iout": {"pressure": 1.0, "temperature": 293.15, "humidity": 50.0},
            },
            "mode": {
                "speed": "2",
                "autoSpeed": "1",
                "flowIn": True,  # codespell:ignore
                "flowOut": True,
                "bypassMode": "0",
                "iaq": 100,
                "temperatureIn": 293.15,
                "temperatureOut": 293.15,
                "humidityIn": 50.0,
                "humidityOut": 50.0,
                "pressureIn": 1.0,
                "pressureOut": 1.0,
                "bypassOn": False,
            },
            "filter": {
                "hepa": {"status": 0, "changed": 0},
                "g4": {"status": 0, "changed": 0},
            },
            "alert": {
                "update_reboot": False,
                "worries": False,
                "ice": False,
                "condensation": False,
                "filterS": 0,
                "filterI": 0,
                "warmup": False,
                "service": False,
                "fault-code": "0",
                "net-fault-code": "0",
                "version": "1.0",
            },
        },
    )

    # Sync methods need MagicMock, not AsyncMock
    mock_vmc.register_websocket_callback = MagicMock()
    mock_vmc.websocket.start = MagicMock()

    return mock_vmc


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.flow_it.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_flow_it() -> Generator[AsyncMock]:
    """Mock FlowItVMCMachine for integration tests."""
    with (
        patch(
            "homeassistant.components.flow_it.FlowItVMCMachine",
            return_value=get_mock_vmc(),
        ) as mock,
        patch(
            "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
            new=mock,
        ),
    ):
        yield mock
