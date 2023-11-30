"""Tests for VeSync common utilities."""
from unittest.mock import MagicMock, call, patch

from homeassistant.components.vesync.common import (
    DOMAIN,
    VeSyncBaseEntity,
    VeSyncDevice,
    VeSyncDeviceHelper,
)
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


async def test_vesyncdevicehelper__is_air_purifier(air_features) -> None:
    """Test helper for detecting a humidifer."""
    with patch(
        "homeassistant.components.vesync.common.humid_features"
    ) as mock_features:
        mock_features.values.side_effect = air_features.values
        mock_features.keys.side_effect = air_features.keys

        helper = VeSyncDeviceHelper()
        assert not helper.humidifier_models
        assert helper.is_humidifier(HUMIDIFIER_MODEL) is False
        assert helper.is_humidifier(FAN_MODEL) is True
        assert helper.humidifier_models == {
            FAN_MODEL,
            "BBB-CCC-DDD",
            "Model2",
            "WWW-XXX-YYY",
        }
        assert mock_features.values.call_count == 1
        assert mock_features.keys.call_count == 1


async def test_vesyncdevicehelper__reset_cache() -> None:
    """Test helper cache reset."""
    helper = VeSyncDeviceHelper()
    assert helper.humidifier_models is None
    assert helper.air_models is None
    helper.is_humidifier("ANYTHING")
    assert helper.humidifier_models is not None
    assert helper.air_models is None
    helper.is_air_purifier("ANYTHING")
    assert helper.humidifier_models is not None
    assert helper.air_models is not None
    helper.reset_cache()
    assert helper.humidifier_models is None
    assert helper.air_models is None


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
    assert device_info["manufacturer"] == "VeSync"
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
