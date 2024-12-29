"""Constants for the SensorPush Cloud tests."""

from __future__ import annotations

from typing import Final

from sensorpush_ha import SensorPushCloudData

from homeassistant.util import dt as dt_util

NUM_MOCK_DEVICES: Final = 3

MOCK_ENTITY_IDS: Final = (
    entity_id
    for i in range(NUM_MOCK_DEVICES)
    for entity_id in (
        f"sensor.test_sensor_name_{i}_altitude",
        f"sensor.test_sensor_name_{i}_atmospheric_pressure",
        f"sensor.test_sensor_name_{i}_battery_voltage",
        f"sensor.test_sensor_name_{i}_dew_point",
        f"sensor.test_sensor_name_{i}_humidity",
        f"sensor.test_sensor_name_{i}_signal_strength",
        f"sensor.test_sensor_name_{i}_temperature",
        f"sensor.test_sensor_name_{i}_vapor_pressure",
    )
)

MOCK_DATA: Final = {
    f"test-sensor-device-id-{i}": SensorPushCloudData(
        device_id=f"test-sensor-device-id-{i}",
        manufacturer=f"test-sensor-manufacturer-{i}",
        model=f"test-sensor-model-{i}",
        name=f"test-sensor-name-{i}",
        altitude=0.0,
        atmospheric_pressure=0.0,
        battery_voltage=0.0,
        dewpoint=0.0,
        humidity=0.0,
        last_update=dt_util.utcnow(),
        signal_strength=0.0,
        temperature=0.0,
        vapor_pressure=0.0,
    )
    for i in range(NUM_MOCK_DEVICES)
}
