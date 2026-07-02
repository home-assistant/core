"""Common fixtures for the Flow-it tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from flow_it_api.models import MachineStatusResponse
import pytest

from homeassistant.components.flow_it.const import DOMAIN

from tests.common import load_json_value_fixture


def get_mock_vmc(
    info_hostname: str = "Flow-it Device",
    state_name: str = "00:11:22:33:44:55",
) -> AsyncMock:
    """Return a mock FlowItVMCMachine."""
    mock_vmc = AsyncMock()
    mock_vmc.get_info.return_value.hostname = info_hostname

    # Load a minimal valid MachineStatusResponse for the fan tests
    json_data = load_json_value_fixture("machine_status.json", DOMAIN)
    json_data["name"] = state_name
    mock_vmc.state = MachineStatusResponse(**json_data)

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
