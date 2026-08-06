"""Tests for the Beatbot sensor platform."""

from types import SimpleNamespace

from beatbot_cloud import BeatbotDeviceData

from homeassistant.components.beatbot.sensor import (
    BeatbotBatterySensor,
    BeatbotErrorSensor,
    BeatbotStatusSensor,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE

DEVICE_ID = "test-device-1"


def _coordinator() -> SimpleNamespace:
    """Return a coordinator with one pool cleaner."""
    device = BeatbotDeviceData(
        device_id=DEVICE_ID,
        product_id="pool-bot-x",
        product_category="pool_clean_bot",
        work_status=5,
        work_mode=0,
        error_code=(1 << 2) | (1 << 6),
        battery_level=80,
        versions=[],
        is_online=True,
    )
    return SimpleNamespace(data={DEVICE_ID: device}, last_update_success=True)


def test_status_sensor() -> None:
    """Expose the library-decoded work status."""
    sensor = BeatbotStatusSensor(_coordinator(), DEVICE_ID)

    assert sensor.unique_id == f"{DEVICE_ID}_status"
    assert sensor.device_class is SensorDeviceClass.ENUM
    assert sensor.native_value == "cleaning"
    assert "standby" in sensor.options


def test_unknown_status() -> None:
    """Return unknown when the library cannot decode a status."""
    coordinator = _coordinator()
    coordinator.data[DEVICE_ID].work_status = 999

    assert BeatbotStatusSensor(coordinator, DEVICE_ID).native_value is None


def test_battery_sensor() -> None:
    """Expose battery percentage with measurement metadata."""
    sensor = BeatbotBatterySensor(_coordinator(), DEVICE_ID)

    assert sensor.unique_id == f"{DEVICE_ID}_battery"
    assert sensor.device_class is SensorDeviceClass.BATTERY
    assert sensor.native_unit_of_measurement == PERCENTAGE
    assert sensor.state_class is SensorStateClass.MEASUREMENT
    assert sensor.native_value == 80


def test_error_sensor() -> None:
    """Expose the first active error from a multi-bit error value."""
    sensor = BeatbotErrorSensor(_coordinator(), DEVICE_ID)

    assert sensor.unique_id == f"{DEVICE_ID}_error"
    assert sensor.device_class is SensorDeviceClass.ENUM
    assert sensor.native_value == "power_low"
    assert "motor_error" in sensor.options


def test_no_error() -> None:
    """Expose none when the device has no active errors."""
    coordinator = _coordinator()
    coordinator.data[DEVICE_ID].error_code = 0

    assert BeatbotErrorSensor(coordinator, DEVICE_ID).native_value == "none"


def test_sensor_availability() -> None:
    """Require the device to be online and coordinator update to succeed."""
    coordinator = _coordinator()
    sensor = BeatbotStatusSensor(coordinator, DEVICE_ID)
    assert sensor.available

    coordinator.data[DEVICE_ID].is_online = False
    assert not sensor.available


def test_sensor_device_info() -> None:
    """Expose Beatbot device metadata through sensor entities."""
    coordinator = _coordinator()
    coordinator.data[DEVICE_ID].name = "AquaSense"
    coordinator.data[DEVICE_ID].model = "AquaSense 2"

    device_info = BeatbotStatusSensor(coordinator, DEVICE_ID).device_info

    assert device_info["identifiers"] == {("beatbot", DEVICE_ID)}
    assert device_info["name"] == "AquaSense"
    assert device_info["manufacturer"] == "Beatbot"
    assert device_info["model"] == "AquaSense 2"
