"""CodSpeed benchmarks for device info conversion and comparison.

Passive bluetooth integrations convert the parsed device info to a ``DeviceInfo``
and compare it with the stored one on every advertisement, which can be many per
second per device.

Run locally with: ``pytest benchmarks --codspeed``.
"""

from pytest_codspeed import BenchmarkFixture
from sensor_state_data import SensorDeviceInfo

from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

_SENSOR_DEVICE_INFO = SensorDeviceInfo(
    name="Benchmark sensor",
    model="B1",
    manufacturer="Benchmark",
    sw_version=None,
    hw_version=None,
)


def test_sensor_device_info_unchanged(benchmark: BenchmarkFixture) -> None:
    """Convert an unchanged sensor device info and compare it with the stored one."""
    stored = sensor_device_info_to_hass_device_info(_SENSOR_DEVICE_INFO)

    def _convert_and_compare() -> bool:
        return stored != sensor_device_info_to_hass_device_info(_SENSOR_DEVICE_INFO)

    assert not benchmark(_convert_and_compare)
