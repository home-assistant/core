"""Common fixtures for the Flow-it tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from flow_it_api.models import MachineStatusResponse
import pytest

from homeassistant.components.flow_it.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_value_fixture


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
            autospec=True,
        ) as mock,
        patch(
            "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
            new=mock,
        ),
    ):
        mock_vmc = mock.return_value

        # Override methods with faulty signatures due to decorators
        mock_vmc.refresh_state = AsyncMock()
        mock_vmc.send_command = AsyncMock()

        mock_vmc.get_info.return_value.hostname = "Flow-it Device"

        json_data = load_json_value_fixture("machine_status.json", DOMAIN)
        json_data["name"] = "001122334455"
        mock_vmc.state = MachineStatusResponse(**json_data)

        mock_vmc.register_websocket_callback = MagicMock()
        mock_vmc.websocket.start = MagicMock()

        yield mock


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Flow-it Device",
        unique_id="001122334455",
        data={
            "host": "http://1.1.1.1",
            "username": "api",
            "password": "test-password",
        },
    )
    entry.add_to_hass(hass)
    return entry
