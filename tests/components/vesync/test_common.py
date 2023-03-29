"""Tests for VeSync common utilities."""
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.vesync.common import (
    DOMAIN,
    VeSyncBaseEntity,
    VeSyncDevice,
    async_process_devices,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .common import FAN_MODEL


async def test_async_process_devices__no_devices(
    hass: HomeAssistant, manager, caplog: pytest.LogCaptureFixture
) -> None:
    """Test when manager with no devices is processed."""
    manager = MagicMock()
    with patch.object(
        hass, "async_add_executor_job", new=AsyncMock()
    ) as mock_add_executor_job:
        devices = await async_process_devices(hass, manager)
        assert mock_add_executor_job.call_count == 1
        assert mock_add_executor_job.call_args[0][0] == manager.update

    assert devices == {
        "fans": [],
        "lights": [],
        "sensors": [],
        "switches": [],
    }
    assert caplog.messages[0] == "0 VeSync fans found"
    assert caplog.messages[1] == "0 VeSync lights found"
    assert caplog.messages[2] == "0 VeSync outlets found"
    assert caplog.messages[3] == "0 VeSync switches found"


async def test_async_process_devices__devices(
    hass: HomeAssistant, manager, caplog: pytest.LogCaptureFixture
) -> None:
    """Test when manager with devices is processed."""
    caplog.set_level(logging.INFO)

    fan = MagicMock()
    fan.device_type = FAN_MODEL
    manager.fans = [fan]

    bulb = MagicMock()
    manager.bulbs = [bulb]

    outlet = MagicMock()
    manager.outlets = [outlet]

    switch = MagicMock()
    switch.is_dimmable.return_value = False
    light = MagicMock()
    light.is_dimmable.return_value = True
    manager.switches = [switch, light]

    with patch.object(
        hass, "async_add_executor_job", new=AsyncMock()
    ) as mock_add_executor_job:
        devices = await async_process_devices(hass, manager)
        assert mock_add_executor_job.call_count == 1
        assert mock_add_executor_job.call_args[0][0] == manager.update

    assert devices == {
        "switches": [outlet, switch],
        "fans": [fan],
        "lights": [bulb, light],
        "sensors": [fan, outlet],
    }
    assert caplog.messages[0] == "1 VeSync fans found"
    assert caplog.messages[1] == "1 VeSync lights found"
    assert caplog.messages[2] == "1 VeSync outlets found"
    assert caplog.messages[3] == "2 VeSync switches found"


async def test_base_entity__init(base_device) -> None:
    """Test the base entity constructor."""
    entity = VeSyncBaseEntity(base_device)

    assert entity.device == base_device
    assert entity.device_class is None
    assert entity.entity_category is None
    assert entity.icon is None
    assert entity.name == "device name"
    assert entity.supported_features is None
    assert entity.unique_id == "cid1"


async def test_base_entity__base_unique_id(base_device) -> None:
    """Test the base entity base_unique_id impl."""
    entity = VeSyncBaseEntity(base_device)

    assert entity.base_unique_id == "cid1"
    base_device.sub_device_no = None
    assert entity.base_unique_id == "cid"


async def test_base_entity__base_name(base_device) -> None:
    """Test the base entity base_name impl."""
    entity = VeSyncBaseEntity(base_device)

    assert entity.base_name == "device name"


async def test_base_entity__available(base_device) -> None:
    """Test the base entity available impl."""
    entity = VeSyncBaseEntity(base_device)

    assert entity.available is True
    base_device.connection_status = "not online"
    assert entity.available is False


async def test_base_entity__device_info(base_device) -> None:
    """Test the base entity device_info impl."""
    entity = VeSyncBaseEntity(base_device)

    device_info: DeviceInfo = entity.device_info
    assert device_info
    assert device_info["identifiers"] == {(DOMAIN, "cid1")}
    assert device_info["name"] == "device name"
    assert device_info["model"] == "device type"
    assert device_info["default_manufacturer"] == "VeSync"
    assert device_info["sw_version"] == 0


async def test_base_entity__update(base_device) -> None:
    """Test the base entity update impl."""
    entity = VeSyncDevice(base_device)

    entity.update()

    assert base_device.update.call_count == 1


async def test_base_device__details(base_device) -> None:
    """Test the base device details impl."""
    device = VeSyncDevice(base_device)

    assert device.details == base_device.details


async def test_base_device__is_on(base_device) -> None:
    """Test the base device is_on impl."""
    device = VeSyncDevice(base_device)

    assert device.is_on is True
    base_device.device_status = "not on"
    assert device.is_on is False


async def test_base_device__turn_off(base_device) -> None:
    """Test the base device turn_on impl."""
    device = VeSyncDevice(base_device)

    device.turn_off()

    assert base_device.turn_off.call_count == 1
