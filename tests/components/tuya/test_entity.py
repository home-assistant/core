"""Tests for Tuya entity description raw_type logic."""

from homeassistant.components.tuya.entity import ElectricityTypeData, RawTypeData
from homeassistant.components.tuya.sensor import TuyaSensorEntityDescription


def test_sensor_entitydescription_default_raw_type() -> None:
    """Test that the default raw_type is ElectricityTypeData."""
    desc = TuyaSensorEntityDescription(key="test")
    assert desc.raw_type is ElectricityTypeData


def test_sensor_entitydescription_rawtype_raw_type() -> None:
    """Test that raw_type can be set to a custom type and used for parsing base64 data."""
    desc = TuyaSensorEntityDescription(key="test", raw_type=RawTypeData)
    b64_str = "fwQAAQB/CQACAX8PAAEBfxUAAgEIEgABAA=="
    obj = desc.raw_type.from_json(b64_str)
    assert isinstance(obj, RawTypeData)
