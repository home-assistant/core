"""Common fixtures for the Compit tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

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
    """Mock CompitApiConnector devices."""

    mock_device_1 = MagicMock()
    mock_device_1.definition.name = "Test Device 1"
    mock_device_1.state = {
        "op_mode": MagicMock(value=1),
    }
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
    mock_device_2.state = {
        "fan_speed": MagicMock(value=2),
    }
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

    all_devices = {1: mock_device_1, 2: mock_device_2, 3: mock_device_3}

    def mock_get_device(device_id: int):
        return all_devices.get(device_id)

    def get_device_parameter(device_id: int, parameter_code: str):
        return all_devices[device_id].state.get(parameter_code)

    def set_device_parameter(device_id: int, parameter_code: str, value: int):
        all_devices[device_id].state[parameter_code] = MagicMock(value=value)
        return True

    mock_instance = MagicMock()
    mock_instance.init = AsyncMock(return_value=True)
    mock_instance.all_devices = all_devices
    mock_instance.get_device_parameter = MagicMock(side_effect=get_device_parameter)
    mock_instance.set_device_parameter = AsyncMock(side_effect=set_device_parameter)
    mock_instance.update_state = AsyncMock()
    mock_instance.get_device = MagicMock(side_effect=mock_get_device)

    with (
        patch(
            "homeassistant.components.compit.CompitApiConnector",
            return_value=mock_instance,
        ),
        patch(
            "homeassistant.components.compit.coordinator.CompitApiConnector",
            return_value=mock_instance,
        ),
    ):
        yield mock_instance
