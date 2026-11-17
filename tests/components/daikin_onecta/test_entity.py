"""Tests for the Daikin Onecta base entity."""

from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.entity import _add_management_point_metadata
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .test_climate_snapshots import _async_setup_fixture


async def test_gateway_device_registry_uses_cloud_metadata(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Register gateway metadata from the config-entry cloud response."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    coordinator = config_entry.runtime_data
    gateway_id, device = next(iter(coordinator.data.items()))
    gateway_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_id), config_entry.entry_id
    )
    assert gateway_entry is not None
    model, serial_number, sw_version = device.gateway_metadata
    assert gateway_entry.name == device.name
    assert gateway_entry.manufacturer == "Daikin"
    assert gateway_entry.model_id == device.device.device_model
    assert gateway_entry.model == model
    assert gateway_entry.serial_number == serial_number
    assert gateway_entry.sw_version == sw_version


def test_add_management_point_metadata_handles_missing_point() -> None:
    """Leave gateway metadata unchanged when the point disappeared."""
    info = DeviceInfo(identifiers={(DOMAIN, "gateway-id")})
    device = MagicMock()
    device.management_point.return_value = None

    _add_management_point_metadata(info, device, "point")

    assert info == DeviceInfo(identifiers={(DOMAIN, "gateway-id")})
    device.management_point.assert_called_once_with("point")
