"""Tests for the Duwi switch entity in Home Assistant."""

import logging
from typing import Generator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from duwi_open_sdk.device_control import ControlDevice
from duwi_open_sdk.device_scene_models import CustomerDevice
from duwi_open_sdk.manager import Manager
from homeassistant.components.duwi import DOMAIN
from homeassistant.components.duwi.base import DuwiEntity
from homeassistant.components.duwi.switch import DuwiSwitchEntity
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def mock_send_commands() -> Generator[AsyncMock, None, None]:
    """Mock the send_commands method of the device manager."""

    async def mock_send_commands(is_group: bool, body: Optional[ControlDevice]):
        # Simulate sending commands and returning a response
        return {"code": "10000"}

    with patch(
        "duwi_open_sdk.manager.CustomerClient.control", new_callable=AsyncMock
    ) as mock_method:
        mock_method.side_effect = mock_send_commands
        yield mock_method


@pytest.fixture
def mock_switch(hass: HomeAssistant, mock_send_commands):
    """Create and provide a mock Duwi switch entity."""
    # Create mock instances for the parameters
    mock_device = MagicMock(spec=CustomerDevice)
    mock_device.device_no = "12345"
    mock_device.is_group = False
    mock_device.value = {
        "switch": "on",
        "online": True,
    }
    mock_manager = MagicMock(spec=Manager)
    mock_description = MagicMock(spec=SwitchEntityDescription)

    # Set expected attributes for mock objects (if needed)
    mock_description.key = "mock_key"
    return DuwiSwitchEntity(
        device=mock_device,
        device_manager=mock_manager,
        description=mock_description,
    )


@pytest.mark.usefixtures
async def test_turn_on(hass: HomeAssistant, mock_switch):
    """Verify the switch turns on as expected."""
    await mock_switch.async_turn_on()
    await hass.async_block_till_done()
    assert mock_switch.is_on, "Switch should be ON."


@pytest.mark.usefixtures
async def test_turn_off(hass: HomeAssistant, mock_switch):
    """Ensure the switch turns off correctly."""
    await mock_switch.async_turn_off()
    await hass.async_block_till_done()
    assert not mock_switch.is_on, "Switch should be OFF."
