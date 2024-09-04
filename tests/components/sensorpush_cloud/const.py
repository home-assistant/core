"""Constants for the SensorPush Cloud tests."""

from __future__ import annotations

from typing import Final

from sensorpush_api import Sample, Samples, Sensor

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

MOCK_SAMPLES: Final = Samples(
    sensors={
        f"test-sensor-id-{i}": [
            Sample(
                altitude=0.0,
                barometric_pressure=0.0,
                dewpoint=0.0,
                humidity=0.0,
                observed=dt_util.utcnow(),
                temperature=0.0,
                vpd=0.0,
            )
        ]
        for i in range(NUM_MOCK_DEVICES)
    }
)

MOCK_SENSORS: Final = {
    f"test-sensor-id-{i}": Sensor(
        active=True,
        address=f"AA:BB:CC:DD:EE:{i:02x}",
        battery_voltage=0.0,
        device_id=f"test-sensor-device-id-{i}",
        id=f"test-sensor-id-{i}",
        name=f"test-sensor-name-{i}",
        rssi=0.0,
        type=f"test-sensor-type-{i}",
    )
    for i in range(NUM_MOCK_DEVICES)
}
