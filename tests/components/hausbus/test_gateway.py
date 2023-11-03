"""Test the hausbus gateway class."""

from unittest.mock import Mock, patch

from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.ModuleId import ModuleId
from pyhausbus.de.hausbus.homeassistant.proxy.controller.params.EFirmwareId import (
    EFirmwareId,
)
from pyhausbus.HomeServer import HomeServer
from pyhausbus.ObjectId import ObjectId

from homeassistant.components.hausbus.gateway import HausbusGateway
from homeassistant.core import HomeAssistant

from .helpers import setup_hausbus_integration


async def test_init(hass: HomeAssistant) -> None:
    """Test initialization of the hausbus gateway."""
    config_entry = setup_hausbus_integration(hass)

    # Create a mock HomeServer
    mock_home_server = Mock(Spec=HomeServer)

    # Patch the HomeServer constructor to return the mock_home_server
    with patch(
        "homeassistant.components.hausbus.gateway.HomeServer",
        return_value=mock_home_server,
    ):
        # Create a HausbusGateway instance
        gateway = HausbusGateway(hass, config_entry)

    # Assert the initial state of the gateway
    assert gateway.hass == hass
    assert gateway.config_entry == config_entry
    assert gateway.bridge_id == "1"
    assert not gateway.devices
    assert not gateway.channels
    assert gateway.home_server == mock_home_server
    assert not gateway._new_channel_listeners


async def test_add_device(hass: HomeAssistant) -> None:
    """Test adding a device to the hausbus gateway."""
    config_entry = setup_hausbus_integration(hass)

    # Create a mock HomeServer
    mock_home_server = Mock(Spec=HomeServer)

    # Patch the HomeServer constructor to return the mock_home_server
    with patch(
        "homeassistant.components.hausbus.gateway.HomeServer",
        return_value=mock_home_server,
    ):
        # Create a HausbusGateway instance
        gateway = HausbusGateway(hass, config_entry)

    # Add a new device
    device_id = "device_1"
    module = ModuleId("module", 0, 1, 0, EFirmwareId.ESP32)
    gateway.add_device(device_id, module)

    # Assert that the device is added to the gateway's devices
    assert device_id in gateway.devices
    assert device_id in gateway.channels


async def test_get_device(hass: HomeAssistant) -> None:
    """Test getting a device from to the hausbus gateway."""
    config_entry = setup_hausbus_integration(hass)

    # Create a mock HomeServer
    mock_home_server = Mock(Spec=HomeServer)

    # Patch the HomeServer constructor to return the mock_home_server
    with patch(
        "homeassistant.components.hausbus.gateway.HomeServer",
        return_value=mock_home_server,
    ):
        # Create a HausbusGateway instance
        gateway = HausbusGateway(hass, config_entry)

    # Add a new device
    device_id = "1"
    module = ModuleId("module", 0, 1, 0, EFirmwareId.ESP32)
    gateway.add_device(device_id, module)

    # Get the device by ObjectId
    object_id = ObjectId(65536)  # = 0x00 01 00 00
    device = gateway.get_device(object_id)

    # Assert that the correct device is retrieved
    assert device.device_id == device_id


# TODO: Add more test cases for other methods and functionality
