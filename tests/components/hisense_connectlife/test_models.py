"""Tests for the Hisense device models."""

from homeassistant.components.hisense_connectlife.const import DeviceType
from homeassistant.components.hisense_connectlife.models import (
    DeviceInfo,
    HisenseApiError,
)

VALID_DEVICE_DATA = {
    "wifiId": "wifi123",
    "deviceId": "dev123",
    "puid": "puid123",
    "deviceNickName": "Test AC",
    "deviceFeatureCode": "19901",
    "deviceFeatureName": "Standard",
    "deviceTypeCode": "009",
    "deviceTypeName": "Air Conditioner",
    "bindTime": "123456",
    "role": "owner",
    "roomId": "room1",
    "roomName": "Living Room",
    "statusList": {
        "t_power": "1",
        "t_mode": "0",
        "t_temp": "25",
        "t_settemp": "24",
        "t_fanspeed": "0",
        "t_swing": "0",
    },
    "useTime": "100",
    "offlineState": 1,
    "seq": 1,
    "createTime": "123456",
}


async def test_device_info_initialization() -> None:
    """Test basic DeviceInfo initialization."""
    device = DeviceInfo(VALID_DEVICE_DATA)

    assert device.wifi_id == "wifi123"
    assert device.device_id == "dev123"
    assert device.puid == "puid123"
    assert device.name == "Test AC"
    assert device.feature_code == "19901"
    assert device.type_code == "009"
    assert device.is_online is True
    assert device.is_onOff is True


async def test_device_info_initialization_invalid_data() -> None:
    """Test DeviceInfo initialization with invalid data."""
    device = DeviceInfo("not a dict")
    assert device.device_id is None
    assert device.status == {}


async def test_is_online() -> None:
    """Test is_online property."""
    data = VALID_DEVICE_DATA.copy()
    data["offlineState"] = 0
    device = DeviceInfo(data)
    assert device.is_online is False

    data["offlineState"] = 1
    device = DeviceInfo(data)
    assert device.is_online is True


async def test_is_onOff() -> None:
    """Test is_onOff property."""
    data = VALID_DEVICE_DATA.copy()
    data["statusList"]["t_power"] = "0"
    device = DeviceInfo(data)
    assert device.is_onOff is False

    data["statusList"]["t_power"] = "1"
    device = DeviceInfo(data)
    assert device.is_onOff is True


async def test_get_device_type() -> None:
    """Test get_device_type method."""
    device = DeviceInfo(VALID_DEVICE_DATA)
    dev_type = device.get_device_type()

    assert isinstance(dev_type, DeviceType)
    assert dev_type.type_code == "009"
    assert dev_type.feature_code == "19901"


async def test_get_device_type_missing_codes() -> None:
    """Test get_device_type with missing codes."""
    data = VALID_DEVICE_DATA.copy()
    data["deviceTypeCode"] = None
    device = DeviceInfo(data)
    assert device.get_device_type() is None


async def test_is_supported() -> None:
    """Test is_supported method."""
    data = VALID_DEVICE_DATA.copy()

    data["deviceTypeCode"] = "009"
    assert DeviceInfo(data).is_supported() is True

    data["deviceTypeCode"] = "999"
    assert DeviceInfo(data).is_supported() is False


async def test_is_devices() -> None:
    """Test is_devices method."""
    data = VALID_DEVICE_DATA.copy()

    data["deviceTypeCode"] = "009"
    assert DeviceInfo(data).is_devices() is True

    data["deviceTypeCode"] = "016"
    assert DeviceInfo(data).is_devices() is True

    data["deviceTypeCode"] = "999"
    assert DeviceInfo(data).is_devices() is False


async def test_is_water() -> None:
    """Test is_water method."""
    data = VALID_DEVICE_DATA.copy()

    data["deviceTypeCode"] = "016"
    assert DeviceInfo(data).is_water() is True

    data["deviceTypeCode"] = "009"
    assert DeviceInfo(data).is_water() is False


async def test_is_humidityr() -> None:
    """Test is_humidityr method."""
    data = VALID_DEVICE_DATA.copy()

    data["deviceTypeCode"] = "007"
    assert DeviceInfo(data).is_humidityr() is True

    data["deviceTypeCode"] = "009"
    assert DeviceInfo(data).is_humidityr() is False


async def test_get_status_value() -> None:
    """Test get_status_value method."""
    device = DeviceInfo(VALID_DEVICE_DATA)
    assert device.get_status_value("t_power") == "1"
    assert device.get_status_value("missing_key", "default") == "default"


async def test_has_attribute() -> None:
    """Test has_attribute method (basic check)."""
    device = DeviceInfo(VALID_DEVICE_DATA)
    mock_parser = type("MockParser", (), {"attributes": {"t_power": {}}})()

    assert device.has_attribute("t_power", mock_parser) is True
    assert device.has_attribute("missing_attr", mock_parser) is False


async def test_to_dict() -> None:
    """Test to_dict method."""
    device = DeviceInfo(VALID_DEVICE_DATA)
    data = device.to_dict()

    assert data["deviceId"] == "dev123"
    assert data["deviceNickName"] == "Test AC"
    assert data["statusList"] == device.status


async def test_debug_info() -> None:
    """Test debug_info method."""
    device = DeviceInfo(VALID_DEVICE_DATA)
    info = device.debug_info()
    assert "Test AC" in info
    assert "009-19901" in info


async def test_set_failed_data() -> None:
    """Test set_failed_data and failed_data property."""
    device = DeviceInfo(VALID_DEVICE_DATA)
    device.set_failed_data(["error1", "error2"])
    assert device.failed_data == ["error1", "error2"]


async def test_hisense_api_error() -> None:
    """Test HisenseApiError exception."""
    exc = HisenseApiError("Test error")
    assert isinstance(exc, Exception)
    assert str(exc) == "Test error"
