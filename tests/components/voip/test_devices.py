"""Test VoIP devices."""

from __future__ import annotations

import pytest
from voip_utils import CallInfo

from homeassistant.components.voip import DOMAIN
from homeassistant.components.voip.devices import VoIPDevice, VoIPDevices
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_device_registry_info(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    call_info: CallInfo,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test info in device registry."""
    voip_device = voip_devices.async_get_or_create(call_info)
    assert not voip_device.async_allow_call(hass)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, call_info.caller_endpoint.uri)}
    )
    assert device is not None
    assert device.name == call_info.caller_endpoint.host
    assert device.manufacturer == "Grandstream"
    assert device.model == "HT801"
    assert device.sw_version == "1.0.17.5"

    # Test we update the device if the fw updates
    call_info.headers["user-agent"] = "Grandstream HT801 2.0.0.0"
    voip_device = voip_devices.async_get_or_create(call_info)

    assert not voip_device.async_allow_call(hass)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, call_info.caller_endpoint.uri)}
    )
    assert device.sw_version == "2.0.0.0"


async def test_device_registry_info_from_unknown_phone(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    call_info: CallInfo,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test info in device registry from unknown phone."""
    call_info.headers["user-agent"] = "Unknown"
    voip_device = voip_devices.async_get_or_create(call_info)
    assert not voip_device.async_allow_call(hass)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, call_info.caller_endpoint.uri)}
    )
    assert device.manufacturer is None
    assert device.model == "Unknown"
    assert device.sw_version is None


async def test_remove_device_registry_entry(
    hass: HomeAssistant,
    voip_device: VoIPDevice,
    voip_devices: VoIPDevices,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing a device registry entry."""
    assert voip_device.voip_id in voip_devices.devices
    assert hass.states.get("switch.192_168_1_210_allow_calls") is not None

    device_registry.async_remove_device(voip_device.device_id)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert hass.states.get("switch.192_168_1_210_allow_calls") is None
    assert voip_device.voip_id not in voip_devices.devices


@pytest.fixture
async def legacy_dev_reg_entry(
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    call_info: CallInfo,
) -> None:
    """Fixture to run before we set up the VoIP integration via fixture."""
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, call_info.caller_ip)},
    )
    entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{call_info.caller_ip}-allow_calls",
        device_id=device.id,
        config_entry=config_entry,
    )
    return device


async def test_device_registry_migration(
    hass: HomeAssistant,
    legacy_dev_reg_entry: dr.DeviceEntry,
    voip_devices: VoIPDevices,
    call_info: CallInfo,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test info in device registry migrates old devices."""
    voip_device = voip_devices.async_get_or_create(call_info)
    new_id = call_info.caller_endpoint.uri
    assert voip_device.voip_id == new_id

    device = device_registry.async_get_device(identifiers={(DOMAIN, new_id)})
    assert device is not None
    assert device.id == legacy_dev_reg_entry.id
    assert device.identifiers == {(DOMAIN, new_id)}
    assert device.name == call_info.caller_endpoint.host
    assert device.manufacturer == "Grandstream"
    assert device.model == "HT801"
    assert device.sw_version == "1.0.17.5"

    assert (
        entity_registry.async_get_entity_id("switch", DOMAIN, f"{new_id}-allow_calls")
        is not None
    )
