"""Tests for the WiiM base entity."""

from wiim.wiim_device import WiimDevice

from homeassistant.components.wiim.const import DOMAIN
from homeassistant.components.wiim.entity import WiimBaseEntity


class MockWiimBaseEntity(WiimBaseEntity):
    """A concrete implementation of WiimBaseEntity for testing purposes."""

    def __init__(self, wiim_device: WiimDevice, entity_id_suffix: str = "test") -> None:
        """Initialize the mock WiimBaseEntity with given device and entity suffix."""
        super().__init__(wiim_device)
        self._attr_unique_id = f"{wiim_device.udn}-{entity_id_suffix}"
        self.entity_id = f"mock.wiim_device_{entity_id_suffix}"


async def test_wiim_base_entity_init(mock_wiim_device: WiimDevice) -> None:
    """Test the initialization of WiimBaseEntity."""
    entity = MockWiimBaseEntity(mock_wiim_device)

    assert entity._device is mock_wiim_device
    assert entity.available == mock_wiim_device.available
    assert entity.unique_id == f"{mock_wiim_device.udn}-test"


async def test_wiim_base_entity_device_info(mock_wiim_device: WiimDevice) -> None:
    """Test the device_info property of WiimBaseEntity."""
    entity = MockWiimBaseEntity(mock_wiim_device)

    device_info = entity.device_info
    assert device_info is not None, "device_info unexpectedly None"
    assert device_info["identifiers"] == {(DOMAIN, mock_wiim_device.udn)}
    assert device_info["name"] == mock_wiim_device.name
    assert device_info["manufacturer"] == mock_wiim_device._manufacturer
    assert device_info["model"] == mock_wiim_device.model_name
    assert device_info["sw_version"] == mock_wiim_device.firmware_version
