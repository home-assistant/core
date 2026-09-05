"""The tests for the xiaomi_miio entity base classes."""

from unittest.mock import Mock

from homeassistant.components.xiaomi_miio.const import DOMAIN
from homeassistant.components.xiaomi_miio.coordinator import GatewayDeviceCoordinator
from homeassistant.components.xiaomi_miio.entity import XiaomiGatewayDevice
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import TEST_MAC

from tests.common import MockConfigEntry


async def test_gateway_sub_device_via_device_id(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test a gateway sub device links to the gateway device via via_device_id."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id=TEST_MAC)
    config_entry.add_to_hass(hass)

    gateway_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, TEST_MAC)},
        manufacturer="Xiaomi",
        name="Test Gateway",
    )

    sub_device = Mock(
        sid="158d0001d7c95a",
        model="lumi.sensor_ht",
        firmware_version="1.2",
        zigbee_model="lumi.sensor_ht.v1",
    )
    sub_device.name = "Sub Device"

    coordinator = GatewayDeviceCoordinator(hass, config_entry, sub_device)
    entity = XiaomiGatewayDevice(coordinator)
    entity.hass = hass

    device_info = entity.device_info

    assert device_info["via_device_id"] == gateway_device.id
