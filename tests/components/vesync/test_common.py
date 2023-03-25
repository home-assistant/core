"""Tests for VeSync common utilities."""
import logging
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from homeassistant.components.vesync.common import (
    DOMAIN,
    VeSyncBaseEntity,
    VeSyncDevice,
    VeSyncDeviceHelper,
    async_process_devices,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .common import FAN_MODEL, HUMIDIFIER_MODEL


async def test_vesyncdevicehelper__get_feature() -> None:
    """Test helper get_feature."""
    mock_device = MagicMock()
    mock_device.dictionary = MagicMock(wraps={"attribute": "value"})

    helper = VeSyncDeviceHelper()
    assert helper.get_feature(mock_device, "dictionary", "attribute") == "value"
    assert mock_device.mock_calls[0] == call.dictionary.get("attribute", None)


async def test_vesyncdevicehelper__get_feature_missing_attribute() -> None:
    """Test helper get_feature."""
    mock_device = MagicMock()
    mock_device.dictionary = MagicMock(wraps={})

    helper = VeSyncDeviceHelper()
    assert helper.get_feature(mock_device, "dictionary", "attribute") is None
    assert mock_device.mock_calls[0] == call.dictionary.get("attribute", None)


async def test_vesyncdevicehelper__has_feature() -> None:
    """Test helper get_feature."""
    mock_device = MagicMock()
    mock_device.dictionary = MagicMock(wraps={"attribute": "value"})

    helper = VeSyncDeviceHelper()
    assert helper.has_feature(mock_device, "dictionary", "attribute") is True
    assert mock_device.mock_calls[0] == call.dictionary.get("attribute", None)


async def test_vesyncdevicehelper__has_feature_none_value() -> None:
    """Test helper get_feature."""
    mock_device = MagicMock()
    mock_device.dictionary = MagicMock(wraps={"attribute": None})

    helper = VeSyncDeviceHelper()
    assert helper.has_feature(mock_device, "dictionary", "attribute") is False
    assert mock_device.mock_calls[0] == call.dictionary.get("attribute", None)


async def test_vesyncdevicehelper__has_feature_missing_attribute() -> None:
    """Test helper get_feature."""
    mock_device = MagicMock()
    mock_device.dictionary = MagicMock(wraps={})

    helper = VeSyncDeviceHelper()
    assert helper.has_feature(mock_device, "dictionary", "attribute") is False
    assert mock_device.mock_calls[0] == call.dictionary.get("attribute", None)


async def test_vesyncdevicehelper__is_humidifier(humid_features) -> None:
    """Test helper for detecting a humidifer."""
    with patch(
        "homeassistant.components.vesync.common.humid_features"
    ) as mock_features:
        mock_features.values.side_effect = humid_features.values
        mock_features.keys.side_effect = humid_features.keys

        helper = VeSyncDeviceHelper()
        assert not helper.humidifier_models
        assert helper.is_humidifier(HUMIDIFIER_MODEL) is True
        assert helper.is_humidifier(FAN_MODEL) is False
        assert helper.humidifier_models == {
            HUMIDIFIER_MODEL,
            "AAA-BBB-CCC",
            "Model2",
            "XXX-YYY-ZZZ",
        }
        assert mock_features.values.call_count == 1
        assert mock_features.keys.call_count == 1


async def test_vesyncdevicehelper__reset_cache() -> None:
    """Test helper cache reset."""
    helper = VeSyncDeviceHelper()
    assert helper.humidifier_models is None
    helper.is_humidifier("ANYTHING")
    assert helper.humidifier_models is not None
    helper.reset_cache()
    assert helper.humidifier_models is None


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
        "humidifiers": [],
        "lights": [],
        "sensors": [],
        "switches": [],
    }
    assert caplog.messages[0] == "0 VeSync fans found"
    assert caplog.messages[1] == "0 VeSync humidifiers found"
    assert caplog.messages[2] == "0 VeSync lights found"
    assert caplog.messages[3] == "0 VeSync outlets found"
    assert caplog.messages[4] == "0 VeSync switches found"


async def test_async_process_devices__devices(
    hass: HomeAssistant, manager, humid_features, caplog: pytest.LogCaptureFixture
) -> None:
    """Test when manager with devices is processed."""
    caplog.set_level(logging.INFO)

    fan = MagicMock()
    fan.device_type = FAN_MODEL
    humidifier1 = MagicMock()
    humidifier1.device_type = HUMIDIFIER_MODEL
    humidifier1.night_light = True
    humidifier2 = MagicMock()
    humidifier2.device_type = HUMIDIFIER_MODEL
    humidifier2.night_light = False
    manager.fans = [fan, humidifier1, humidifier2]

    bulb = MagicMock()
    manager.bulbs = [bulb]

    outlet = MagicMock()
    manager.outlets = [outlet]

    switch = MagicMock()
    switch.is_dimmable.return_value = False
    light = MagicMock()
    light.is_dimmable.return_value = True
    manager.switches = [switch, light]

    with patch(
        "homeassistant.components.vesync.common.humid_features"
    ) as mock_features, patch.object(
        hass, "async_add_executor_job", new=AsyncMock()
    ) as mock_add_executor_job:
        mock_features.values.side_effect = humid_features.values
        mock_features.keys.side_effect = humid_features.keys

        devices = await async_process_devices(hass, manager)
        assert mock_add_executor_job.call_count == 1
        assert mock_add_executor_job.call_args[0][0] == manager.update

    assert devices == {
        "fans": [fan],
        "humidifiers": [humidifier1, humidifier2],
        "lights": [fan, humidifier1, humidifier2, bulb, light],
        "sensors": [fan, humidifier1, humidifier2, outlet],
        "switches": [fan, humidifier1, humidifier2, outlet, switch],
    }
    assert caplog.messages[0] == "1 VeSync fans found"
    assert caplog.messages[1] == "2 VeSync humidifiers found"
    assert caplog.messages[2] == "1 VeSync lights found"
    assert caplog.messages[3] == "1 VeSync outlets found"
    assert caplog.messages[4] == "2 VeSync switches found"


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
