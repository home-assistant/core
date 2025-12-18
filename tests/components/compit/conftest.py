"""Common fixtures for the Compit tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.compit.const import DOMAIN
from homeassistant.const import CONF_EMAIL

from .consts import CONFIG_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT,
        unique_id=CONFIG_INPUT[CONF_EMAIL],
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.compit.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_compit_api() -> Generator[AsyncMock]:
    """Mock CompitApiConnector."""
    with patch(
        "homeassistant.components.compit.config_flow.CompitApiConnector.init",
    ) as mock_api:
        yield mock_api


@pytest.fixture
def mock_connector():
    """Create a mock CompitApiConnector."""
    connector = MagicMock()

    mock_device_1 = MagicMock()
    mock_device_1.definition.name = "Test Device 1"
    mock_device_1.definition.parameters = [
        MagicMock(
            type="Select",
            label="Operation Mode",
            parameter_code="op_mode",
            details=[
                MagicMock(description="Auto", state=0),
                MagicMock(description="Manual", state=1),
                MagicMock(description="Off", state=2),
            ],
        ),
        MagicMock(
            type="Number",
            label="Temperature",
            parameter_code="temp",
        ),
    ]

    mock_device_2 = MagicMock()
    mock_device_2.definition.name = "Test Device 2"
    mock_device_2.definition.parameters = [
        MagicMock(
            type="Select",
            label="Fan Speed",
            parameter_code="fan_speed",
            details=[
                MagicMock(description="Low", state=1),
                MagicMock(description="Medium", state=2),
                MagicMock(description="High", state=3),
            ],
        ),
    ]

    mock_device_3 = MagicMock()
    mock_device_3.definition.name = "Test Device 3"
    mock_device_3.definition.parameters = None

    connector.all_devices = {1: mock_device_1, 2: mock_device_2, 3: mock_device_3}

    def mock_get_device(device_id: int):
        return connector.all_devices.get(device_id)

    connector.get_device.side_effect = mock_get_device

    def mock_get_device_parameter(device_id, parameter_code):
        if device_id == 1 and parameter_code == "op_mode":
            return MagicMock(value=0)  # Auto mode
        if device_id == 2 and parameter_code == "fan_speed":
            return MagicMock(value=2)  # Medium speed
        return None

    connector.get_device_parameter.side_effect = mock_get_device_parameter
    connector.set_device_parameter = AsyncMock()

    return connector


@pytest.fixture
def mock_coordinator(mock_connector):
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.connector = mock_connector
    coordinator.data = mock_connector.all_devices
    coordinator.last_update_success = True
    coordinator.async_config_entry_first_refresh = AsyncMock()

    # Add properties to support CoordinatorEntity
    type(coordinator).available = PropertyMock(return_value=True)

    return coordinator
