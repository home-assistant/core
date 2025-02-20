"""Test for GryfSmartConfigFlow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.gryfsmart.config_flow import (
    GryfSmartConfigFlow,
    ping_connection,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_ping_connection_success():
    """Mock the ping_connection to simulate successful connection."""
    with patch(
        "homeassistant.components.gryfsmart.config_flow.ping_connection",
        return_value=True,
    ):
        yield


@pytest.fixture
def mock_ping_connection_failure():
    """Mock the ping_connection to simulate connection failure."""
    with patch(
        "homeassistant.components.gryfsmart.config_flow.ping_connection",
        return_value=False,
    ):
        yield


@pytest.fixture
def mock_create_entry():
    """Mock creating a config entry."""
    with patch(
        "homeassistant.components.gryfsmart.config_flow.GryfSmartConfigFlow.async_create_entry"
    ) as mock:
        mock.return_value = {"type": "form"}
        yield mock


@pytest.fixture
async def config_flow(hass: HomeAssistant):
    """Fixture to create an instance of the config flow."""

    await async_setup_component(hass, "config", {})

    config_flow = GryfSmartConfigFlow()
    config_flow._edit_index = 0

    hass.config_entries = MagicMock()

    return config_flow


async def test_step_user_success(config_flow, mock_ping_connection_success) -> None:
    """Test the user input step for a valid configuration."""
    user_input = {"port": "/dev/ttyUSB0", "module_count": 2}

    result = await config_flow.async_step_user(user_input)

    assert result["type"] == "menu"
    assert result["step_id"] == "device_menu"


async def test_step_add_device(config_flow) -> None:
    """Test adding a new device."""
    user_input = {"type": "sensor", "name": "Sensor 1", "id": 1234, "extra": 10}

    result = await config_flow.async_step_add_device(user_input)

    assert len(config_flow._config_data["devices"]) == 1
    assert config_flow._config_data["devices"][0]["name"] == "Sensor 1"
    assert result["type"] == "menu"


async def test_step_edit_device(config_flow) -> None:
    """Test editing an existing device."""
    user_input = {"type": "sensor", "name": "Sensor 1", "id": 1234}
    await config_flow.async_step_add_device(user_input)

    user_input_edit = {
        "type": "sensor",
        "name": "Updated Sensor 1",
        "id": 5678,
        "extra": 20,
    }

    result = await config_flow.async_step_edit_device_details(user_input_edit)

    assert config_flow._config_data["devices"][0]["name"] == "Updated Sensor 1"
    assert result["type"] == "menu"


async def test_step_finish(config_flow, mock_create_entry) -> None:
    """Test finishing the config flow."""

    user_input = {"port": "/dev/ttyUSB0", "module_count": 2}
    await config_flow.async_step_user(user_input)

    result = await config_flow.async_step_finish()

    mock_create_entry.assert_called_once()

    assert result["type"] == "form"


async def test_ping_connection_success(mock_ping_connection_success) -> None:
    """Test the ping_connection function for success."""
    result = await ping_connection("/dev/ttyUSB0")
    assert result is True


async def test_ping_connection_failure(mock_ping_connection_failure) -> None:
    """Test the ping_connection function for failure."""
    result = await ping_connection("/dev/invalid")
    assert result is False
