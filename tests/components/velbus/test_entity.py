"""Tests for the Velbus entity base class."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from velbusaio.channels import Channel as VelbusChannel

from homeassistant.components.velbus.const import DOMAIN
from homeassistant.components.velbus.entity import VelbusEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo


@pytest.mark.parametrize(
    ("module_serial", "expected_unique_id"),
    [
        ("a1b2c3d4e5f6", "a1b2c3d4e5f6-2"),
        (None, "5-2"),
        ("", "5-2"),
        # Modules like the VMB4RY report a serial of "0"; without a fallback two
        # such modules would share the same unique_id.
        ("0", "5-2"),
    ],
)
def test_unique_id_falls_back_to_module_address(
    module_serial: str | None, expected_unique_id: str
) -> None:
    """Test that a missing or "0" module serial falls back to the module address."""
    channel = AsyncMock(spec=VelbusChannel)
    channel.get_module_address.return_value = 5
    channel.get_channel_number.return_value = 2
    channel.get_module_serial.return_value = module_serial
    channel.get_name.return_value = "channel"
    channel.is_sub_device.return_value = False

    entity = VelbusEntity(channel)

    assert entity.unique_id == expected_unique_id
    assert entity._attr_name == "channel"


def _channel_mock(*, sub_device: bool) -> AsyncMock:
    channel = AsyncMock(spec=VelbusChannel)
    channel.get_module_address.return_value = 88
    channel.get_channel_number.return_value = 9
    channel.get_name.return_value = "CoverName"
    channel.get_full_name.return_value = "Kitchen (VMB2BLE) - CoverName"
    channel.get_module_type_name.return_value = "VMB2BLE"
    channel.get_module_type.return_value = 123
    channel.get_module_sw_version.return_value = "2.0.0"
    channel.get_module_serial.return_value = "serial"
    channel.is_sub_device.return_value = sub_device
    return channel


def test_device_info_module_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test device_info for entities on the module device."""
    channel = _channel_mock(sub_device=False)
    entity = VelbusEntity(channel)
    entity.hass = hass
    entity.platform = MagicMock()
    entity.platform.config_entry = config_entry

    device_info = entity.device_info

    assert isinstance(device_info, DeviceInfo)
    assert device_info.identifiers == {(DOMAIN, "88")}
    assert device_info.name == "Kitchen (VMB2BLE) - CoverName"
    assert device_info.manufacturer == "Velleman"


def test_device_info_child_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device_info for entities on a channel child device."""
    parent = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "88")},
        name="Kitchen (VMB2BLE)",
        manufacturer="Velleman",
        model="VMB2BLE",
    )
    channel = _channel_mock(sub_device=True)
    entity = VelbusEntity(channel)
    entity.hass = hass
    entity.platform = MagicMock()
    entity.platform.config_entry = config_entry

    device_info = entity.device_info

    assert isinstance(device_info, ChildDeviceInfo)
    assert device_info.identifiers == {(DOMAIN, "88-9")}
    assert device_info.name == "CoverName"
    assert device_info.parent_device_id == parent.id
    assert entity._attr_name is None
