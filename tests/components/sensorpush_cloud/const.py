"""Constants for the SensorPush Cloud tests."""

from sensorpush_ha import SensorPushCloudData

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.util import dt as dt_util

CONF_DATA = {
    CONF_EMAIL: "test@example.com",
    CONF_PASSWORD: "test-password",
}

NUM_MOCK_DEVICES = 3

MOCK_DATA = {
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
