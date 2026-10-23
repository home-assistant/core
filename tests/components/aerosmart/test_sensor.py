"""Tests for the aerosmart sensor platform."""

from homeassistant.components.aerosmart.sensor import SENSOR_DESCRIPTIONS
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass


def test_volume_device_classes() -> None:
    """Volume and flow entities expose their matching device classes."""
    expected = {
        "coarse_dust_filter_maximum_conveyed_volume": (SensorDeviceClass.VOLUME),
        "total_conveyed_air_volume": SensorDeviceClass.VOLUME,
        "conveyed_air_volume_since_filter_change": (SensorDeviceClass.VOLUME),
        "target_extract_airflow": (SensorDeviceClass.VOLUME_FLOW_RATE),
        "target_supply_airflow": (SensorDeviceClass.VOLUME_FLOW_RATE),
    }

    assert {
        description.key: description.device_class
        for description in SENSOR_DESCRIPTIONS
        if description.key in expected
    } == expected


def test_filter_change_volume_is_a_total_increasing_counter() -> None:
    """The filter-change counter records accumulated conveyed volume."""
    descriptions = {description.key: description for description in SENSOR_DESCRIPTIONS}

    assert (
        descriptions["conveyed_air_volume_since_filter_change"].state_class
        is SensorStateClass.TOTAL_INCREASING
    )


def test_volume_limit_has_no_state_class() -> None:
    """A configured volume limit is not an accumulating measurement."""
    descriptions = {description.key: description for description in SENSOR_DESCRIPTIONS}

    assert (
        descriptions["coarse_dust_filter_maximum_conveyed_volume"].state_class is None
    )


def test_central_unit_address_has_no_state_class() -> None:
    """A controller address is an identifier, not a measurement."""
    descriptions = {description.key: description for description in SENSOR_DESCRIPTIONS}

    assert descriptions["heat_pump_central_unit_address"].state_class is None
