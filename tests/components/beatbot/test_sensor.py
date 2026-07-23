"""Tests for Beatbot sensor category support."""

from types import SimpleNamespace

from homeassistant.components.beatbot.iot.category import (
    BATTERY_CATEGORIES,
    CATEGORY_MAP,
    ERROR_BITS_BY_CATEGORY,
)
from homeassistant.components.beatbot.models import BeatbotDeviceData
from homeassistant.components.beatbot.sensor import BeatbotErrorSensor

DEVICE_ID = "test-device-1"


def test_clean_base_station_has_no_battery() -> None:
    """The mains-powered clean base station must not get a battery entity."""
    category = CATEGORY_MAP["clean_base_station"]

    assert category not in BATTERY_CATEGORIES


def test_mobile_devices_have_battery() -> None:
    """Mobile product categories retain their battery entities."""
    assert CATEGORY_MAP["pool_clean_bot"] in BATTERY_CATEGORIES
    assert CATEGORY_MAP["lawn_mower"] in BATTERY_CATEGORIES


def test_error_sensor_exposes_all_active_error_bits() -> None:
    """Expose every active bit while using the lowest bit as primary state."""
    category = CATEGORY_MAP["pool_clean_bot"]
    bits = ERROR_BITS_BY_CATEGORY[category]
    device = BeatbotDeviceData(
        device_id=DEVICE_ID,
        product_id="pool-bot-x",
        product_category="pool_clean_bot",
        work_status=0,
        work_mode=0,
        error_code=(1 << 2) | (1 << 6),
        battery_level=80,
        versions=[],
        is_online=True,
    )
    sensor = BeatbotErrorSensor(
        SimpleNamespace(data={DEVICE_ID: device}), DEVICE_ID, bits
    )

    assert sensor.native_value == "power_low"
    assert sensor.extra_state_attributes["power_low"] is True
    assert sensor.extra_state_attributes["motor_error"] is True
    assert sensor.extra_state_attributes["dust_box_full"] is False
