"""Test the BTHome sensors."""

from datetime import timedelta
import logging
import time

import pytest

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.components.bthome.const import CONF_SLEEPY_DEVICE, DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import make_bthome_v1_adv, make_bthome_v2_adv, make_encrypted_bthome_v1_adv

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)

_LOGGER = logging.getLogger(__name__)


# Tests for BTHome v1
@pytest.mark.parametrize(
    ("mac_address", "advertisement", "bind_key", "result"),
    [
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v1_adv(
                "A4:C1:38:8D:18:B2",
                b"#\x02\xca\t\x03\x03\xbf\x13",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_temperature",
                    "friendly_name": "Test Device 18B2 Temperature",
                    "unit_of_measurement": "°C",
                    "state_class": "measurement",
                    "expected_state": "25.06",
                },
                {
                    "sensor_entity": "sensor.test_device_18b2_humidity",
                    "friendly_name": "Test Device 18B2 Humidity",
                    "unit_of_measurement": "%",
                    "state_class": "measurement",
                    "expected_state": "50.55",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v1_adv(
                "A4:C1:38:8D:18:B2",
                b"\x02\x00\xa8#\x02]\t\x03\x03\xb7\x18\x02\x01]",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_temperature",
                    "friendly_name": "Test Device 18B2 Temperature",
                    "unit_of_measurement": "°C",
                    "state_class": "measurement",
                    "expected_state": "23.97",
                },
                {
                    "sensor_entity": "sensor.test_device_18b2_humidity",
                    "friendly_name": "Test Device 18B2 Humidity",
                    "unit_of_measurement": "%",
                    "state_class": "measurement",
                    "expected_state": "63.27",
                },
                {
                    "sensor_entity": "sensor.test_device_18b2_battery",
                    "friendly_name": "Test Device 18B2 Battery",
                    "unit_of_measurement": "%",
                    "state_class": "measurement",
                    "expected_state": "93",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v1_adv(
                "A4:C1:38:8D:18:B2",
                b"\x02\x00\x0c\x04\x04\x13\x8a\x01",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_pressure",
                    "friendly_name": "Test Device 18B2 Pressure",
                    "unit_of_measurement": "mbar",
                    "state_class": "measurement",
                    "expected_state": "1008.83",
                },
            ],
        ),
        (
            "AA:BB:CC:DD:EE:FF",
            make_bthome_v1_adv(
                "AA:BB:CC:DD:EE:FF",
                b"\x04\x05\x13\x8a\x14",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_eeff_illuminance",
                    "friendly_name": "Test Device EEFF Illuminance",
                    "unit_of_measurement": "lx",
                    "state_class": "measurement",
                    "expected_state": "13460.67",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v1_adv(
                "A4:C1:38:8D:18:B2",
                b"\x03\x06\x5e\x1f",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_mass",
                    "friendly_name": "Test Device 18B2 Mass",
                    "unit_of_measurement": "kg",
                    "state_class": "measurement",
                    "expected_state": "80.3",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v1_adv(
                "A4:C1:38:8D:18:B2",
                b"\x03\x07\x3e\x1d",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_mass",
                    "friendly_name": "Test Device 18B2 Mass",
                    "unit_of_measurement": "lb",
                    "state_class": "measurement",
                    "expected_state": "74.86",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v1_adv(
                "A4:C1:38:8D:18:B2",
                b"\x23\x08\xca\x06",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_dew_point",
                    "friendly_name": "Test Device 18B2 Dew Point",
                    "unit_of_measurement": "°C",
                    "state_class": "measurement",
                    "expected_state": "17.38",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v1_adv(
                "A4:C1:38:8D:18:B2",
                b"\x02\x09\x60",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_count",
                    "friendly_name": "Test Device 18B2 Count",
                    "state_class": "measurement",
                    "expected_state": "96",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v1_adv(
                "A4:C1:38:8D:18:B2",
                b"\x04\n\x13\x8a\x14",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_energy",
                    "friendly_name": "Test Device 18B2 Energy",
                    "unit_of_measurement": "kWh",
                    "state_class": "total",
                    "expected_state": "1346.067",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v1_adv(
                "A4:C1:38:8D:18:B2",
                b"\x04\x0b\x02\x1b\x00",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_power",
                    "friendly_name": "Test Device 18B2 Power",
                    "unit_of_measurement": "W",
                    "state_class": "measurement",
                    "expected_state": "69.14",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v1_adv(
                "A4:C1:38:8D:18:B2",
                b"\x03\x0c\x02\x0c",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_voltage",
                    "friendly_name": "Test Device 18B2 Voltage",
                    "unit_of_measurement": "V",
                    "state_class": "measurement",
                    "expected_state": "3.074",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v1_adv(
                "A4:C1:38:8D:18:B2",
                b"\x03\r\x12\x0c\x03\x0e\x02\x1c",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_pm10",
                    "friendly_name": "Test Device 18B2 Pm10",
                    "unit_of_measurement": "µg/m³",
                    "state_class": "measurement",
                    "expected_state": "7170",
                },
                {
                    "sensor_entity": "sensor.test_device_18b2_pm25",
                    "friendly_name": "Test Device 18B2 Pm25",
                    "unit_of_measurement": "µg/m³",
                    "state_class": "measurement",
                    "expected_state": "3090",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v1_adv(
                "A4:C1:38:8D:18:B2",
                b"\x03\x12\xe2\x04",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_carbon_dioxide",
                    "friendly_name": "Test Device 18B2 Carbon Dioxide",
                    "unit_of_measurement": "ppm",
                    "state_class": "measurement",
                    "expected_state": "1250",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v1_adv(
                "A4:C1:38:8D:18:B2",
                b"\x03\x133\x01",
            ),
            None,
            [
                {
                    "sensor_entity": (
                        "sensor.test_device_18b2_volatile_organic_compounds"
                    ),
                    "friendly_name": "Test Device 18B2 Volatile Organic Compounds",
                    "unit_of_measurement": "µg/m³",
                    "state_class": "measurement",
                    "expected_state": "307",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v1_adv(
                "A4:C1:38:8D:18:B2",
                b"\x03\x14\x02\x0c",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_moisture",
                    "friendly_name": "Test Device 18B2 Moisture",
                    "unit_of_measurement": "%",
                    "state_class": "measurement",
                    "expected_state": "30.74",
                },
            ],
        ),
        (
            "54:48:E6:8F:80:A5",
            make_encrypted_bthome_v1_adv(
                "54:48:E6:8F:80:A5",
                b'\xfb\xa45\xe4\xd3\xc3\x12\xfb\x00\x11"3W\xd9\n\x99',
            ),
            "231d39c1d7cc1ab1aee224cd096db932",
            [
                {
                    "sensor_entity": "sensor.atc_80a5_temperature",
                    "friendly_name": "ATC 80A5 Temperature",
                    "unit_of_measurement": "°C",
                    "state_class": "measurement",
                    "expected_state": "25.06",
                },
                {
                    "sensor_entity": "sensor.atc_80a5_humidity",
                    "friendly_name": "ATC 80A5 Humidity",
                    "unit_of_measurement": "%",
                    "state_class": "measurement",
                    "expected_state": "50.55",
                },
            ],
        ),
    ],
)
async def test_v1_sensors(
    hass: HomeAssistant,
    mac_address,
    advertisement,
    bind_key,
    result,
) -> None:
    """Test the different BTHome V1 sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=mac_address,
        data={"bindkey": bind_key},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        advertisement,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == len(result)

    for meas in result:
        sensor = hass.states.get(meas["sensor_entity"])
        sensor_attr = sensor.attributes
        assert sensor.state == meas["expected_state"]
        assert sensor_attr[ATTR_FRIENDLY_NAME] == meas["friendly_name"]
        if ATTR_UNIT_OF_MEASUREMENT in sensor_attr:
            # Some sensors don't have a unit of measurement
            assert sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == meas["unit_of_measurement"]
        assert sensor_attr[ATTR_STATE_CLASS] == meas["state_class"]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


# Tests for BTHome V2
@pytest.mark.parametrize(
    ("mac_address", "advertisement", "bind_key", "result"),
    [
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x02\xca\x09\x03\xbf\x13",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_temperature",
                    "friendly_name": "Test Device 18B2 Temperature",
                    "unit_of_measurement": "°C",
                    "state_class": "measurement",
                    "expected_state": "25.06",
                },
                {
                    "sensor_entity": "sensor.test_device_18b2_humidity",
                    "friendly_name": "Test Device 18B2 Humidity",
                    "unit_of_measurement": "%",
                    "state_class": "measurement",
                    "expected_state": "50.55",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x01\x5d\x02\x5d\x09\x03\xb7\x18",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_temperature",
                    "friendly_name": "Test Device 18B2 Temperature",
                    "unit_of_measurement": "°C",
                    "state_class": "measurement",
                    "expected_state": "23.97",
                },
                {
                    "sensor_entity": "sensor.test_device_18b2_humidity",
                    "friendly_name": "Test Device 18B2 Humidity",
                    "unit_of_measurement": "%",
                    "state_class": "measurement",
                    "expected_state": "63.27",
                },
                {
                    "sensor_entity": "sensor.test_device_18b2_battery",
                    "friendly_name": "Test Device 18B2 Battery",
                    "unit_of_measurement": "%",
                    "state_class": "measurement",
                    "expected_state": "93",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x04\x13\x8a\x01",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_pressure",
                    "friendly_name": "Test Device 18B2 Pressure",
                    "unit_of_measurement": "mbar",
                    "state_class": "measurement",
                    "expected_state": "1008.83",
                },
            ],
        ),
        (
            "AA:BB:CC:DD:EE:FF",
            make_bthome_v2_adv(
                "AA:BB:CC:DD:EE:FF",
                b"\x40\x05\x13\x8a\x14",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_eeff_illuminance",
                    "friendly_name": "Test Device EEFF Illuminance",
                    "unit_of_measurement": "lx",
                    "state_class": "measurement",
                    "expected_state": "13460.67",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x06\x5e\x1f",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_mass",
                    "friendly_name": "Test Device 18B2 Mass",
                    "unit_of_measurement": "kg",
                    "state_class": "measurement",
                    "expected_state": "80.3",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x07\x3e\x1d",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_mass",
                    "friendly_name": "Test Device 18B2 Mass",
                    "unit_of_measurement": "lb",
                    "state_class": "measurement",
                    "expected_state": "74.86",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x08\xca\x06",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_dew_point",
                    "friendly_name": "Test Device 18B2 Dew Point",
                    "unit_of_measurement": "°C",
                    "state_class": "measurement",
                    "expected_state": "17.38",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x44\x09\x60",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_count",
                    "friendly_name": "Test Device 18B2 Count",
                    "state_class": "measurement",
                    "expected_state": "96",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x0a\x13\x8a\x14",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_energy",
                    "friendly_name": "Test Device 18B2 Energy",
                    "unit_of_measurement": "kWh",
                    "state_class": "total",
                    "expected_state": "1346.067",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x0b\x02\x1b\x00",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_power",
                    "friendly_name": "Test Device 18B2 Power",
                    "unit_of_measurement": "W",
                    "state_class": "measurement",
                    "expected_state": "69.14",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x0c\x02\x0c",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_voltage",
                    "friendly_name": "Test Device 18B2 Voltage",
                    "unit_of_measurement": "V",
                    "state_class": "measurement",
                    "expected_state": "3.074",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x0d\x12\x0c\x0e\x02\x1c",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_pm10",
                    "friendly_name": "Test Device 18B2 Pm10",
                    "unit_of_measurement": "µg/m³",
                    "state_class": "measurement",
                    "expected_state": "7170",
                },
                {
                    "sensor_entity": "sensor.test_device_18b2_pm25",
                    "friendly_name": "Test Device 18B2 Pm25",
                    "unit_of_measurement": "µg/m³",
                    "state_class": "measurement",
                    "expected_state": "3090",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x12\xe2\x04",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_carbon_dioxide",
                    "friendly_name": "Test Device 18B2 Carbon Dioxide",
                    "unit_of_measurement": "ppm",
                    "state_class": "measurement",
                    "expected_state": "1250",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x133\x01",
            ),
            None,
            [
                {
                    "sensor_entity": (
                        "sensor.test_device_18b2_volatile_organic_compounds"
                    ),
                    "friendly_name": "Test Device 18B2 Volatile Organic Compounds",
                    "unit_of_measurement": "µg/m³",
                    "state_class": "measurement",
                    "expected_state": "307",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x14\x02\x0c",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_moisture",
                    "friendly_name": "Test Device 18B2 Moisture",
                    "unit_of_measurement": "%",
                    "state_class": "measurement",
                    "expected_state": "30.74",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x3f\x02\x0c",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_rotation",
                    "friendly_name": "Test Device 18B2 Rotation",
                    "unit_of_measurement": "°",
                    "state_class": "measurement",
                    "expected_state": "307.4",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x40\x0c\x00",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_distance",
                    "friendly_name": "Test Device 18B2 Distance",
                    "unit_of_measurement": "mm",
                    "state_class": "measurement",
                    "expected_state": "12",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x41\x4e\x00",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_distance",
                    "friendly_name": "Test Device 18B2 Distance",
                    "unit_of_measurement": "m",
                    "state_class": "measurement",
                    "expected_state": "7.8",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x42\x4e\x34\x00",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_duration",
                    "friendly_name": "Test Device 18B2 Duration",
                    "unit_of_measurement": "s",
                    "state_class": "measurement",
                    "expected_state": "13.39",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x43\x4e\x34",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_current",
                    "friendly_name": "Test Device 18B2 Current",
                    "unit_of_measurement": "A",
                    "state_class": "measurement",
                    "expected_state": "13.39",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x44\x4e\x34",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_speed",
                    "friendly_name": "Test Device 18B2 Speed",
                    "unit_of_measurement": "m/s",
                    "state_class": "measurement",
                    "expected_state": "133.9",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x45\x11\x01",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_temperature",
                    "friendly_name": "Test Device 18B2 Temperature",
                    "unit_of_measurement": "°C",
                    "state_class": "measurement",
                    "expected_state": "27.3",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x46\x32",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_uv_index",
                    "friendly_name": "Test Device 18B2 Uv Index",
                    "state_class": "measurement",
                    "expected_state": "5.0",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x47\x87\x56",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_volume",
                    "friendly_name": "Test Device 18B2 Volume",
                    "unit_of_measurement": "L",
                    "state_class": "total",
                    "expected_state": "2215.1",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x48\xdc\x87",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_volume",
                    "friendly_name": "Test Device 18B2 Volume",
                    "unit_of_measurement": "mL",
                    "state_class": "total",
                    "expected_state": "34780",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x49\xdc\x87",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_volume_flow_rate",
                    "friendly_name": "Test Device 18B2 Volume Flow Rate",
                    "unit_of_measurement": "m³/h",
                    "state_class": "measurement",
                    "expected_state": "34.78",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x44\x50\x5d\x39\x61\x64",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_timestamp",
                    "friendly_name": "Test Device 18B2 Timestamp",
                    "state_class": None,
                    "expected_state": "2023-05-14T19:41:17+00:00",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x44\x51\x87\x56",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_acceleration",
                    "friendly_name": "Test Device 18B2 Acceleration",
                    "unit_of_measurement": "m/s²",
                    "state_class": "measurement",
                    "expected_state": "22.151",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x44\x52\x87\x56",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_gyroscope",
                    "friendly_name": "Test Device 18B2 Gyroscope",
                    "unit_of_measurement": "°/s",
                    "state_class": "measurement",
                    "expected_state": "22.151",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x4b\x13\x8a\x14",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_gas",
                    "friendly_name": "Test Device 18B2 Gas",
                    "unit_of_measurement": "m³",
                    "state_class": "total",
                    "expected_state": "1346.067",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x4f\x87\x56\x2a\x01",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_water",
                    "friendly_name": "Test Device 18B2 Water",
                    "unit_of_measurement": "L",
                    "state_class": "total",
                    "expected_state": "19551.879",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x44\x53\x0c\x48\x65\x6c\x6c\x6f\x20\x57\x6f\x72\x6c\x64\x21",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_text",
                    "friendly_name": "Test Device 18B2 Text",
                    "expected_state": "Hello World!",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x44\x54\x0c\x48\x65\x6c\x6c\x6f\x20\x57\x6f\x72\x6c\x64\x21",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_raw",
                    "friendly_name": "Test Device 18B2 Raw",
                    "expected_state": "48656c6c6f20576f726c6421",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x55\x87\x56\x2a\x01",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_volume_storage",
                    "friendly_name": "Test Device 18B2 Volume Storage",
                    "unit_of_measurement": "L",
                    "state_class": "measurement",
                    "expected_state": "19551.879",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x02\xca\x09\x02\xcf\x09",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_temperature_1",
                    "friendly_name": "Test Device 18B2 Temperature 1",
                    "unit_of_measurement": "°C",
                    "state_class": "measurement",
                    "expected_state": "25.06",
                },
                {
                    "sensor_entity": "sensor.test_device_18b2_temperature_2",
                    "friendly_name": "Test Device 18B2 Temperature 2",
                    "unit_of_measurement": "°C",
                    "state_class": "measurement",
                    "expected_state": "25.11",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x02\xca\x09\x02\xcf\x09\x02\xcf\x08\x03\xb7\x18\x03\xb7\x17\x01\x5d",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_temperature_1",
                    "friendly_name": "Test Device 18B2 Temperature 1",
                    "unit_of_measurement": "°C",
                    "state_class": "measurement",
                    "expected_state": "25.06",
                },
                {
                    "sensor_entity": "sensor.test_device_18b2_temperature_2",
                    "friendly_name": "Test Device 18B2 Temperature 2",
                    "unit_of_measurement": "°C",
                    "state_class": "measurement",
                    "expected_state": "25.11",
                },
                {
                    "sensor_entity": "sensor.test_device_18b2_temperature_3",
                    "friendly_name": "Test Device 18B2 Temperature 3",
                    "unit_of_measurement": "°C",
                    "state_class": "measurement",
                    "expected_state": "22.55",
                },
                {
                    "sensor_entity": "sensor.test_device_18b2_humidity_1",
                    "friendly_name": "Test Device 18B2 Humidity 1",
                    "unit_of_measurement": "%",
                    "state_class": "measurement",
                    "expected_state": "63.27",
                },
                {
                    "sensor_entity": "sensor.test_device_18b2_humidity_2",
                    "friendly_name": "Test Device 18B2 Humidity 2",
                    "unit_of_measurement": "%",
                    "state_class": "measurement",
                    "expected_state": "60.71",
                },
                {
                    "sensor_entity": "sensor.test_device_18b2_battery",
                    "friendly_name": "Test Device 18B2 Battery",
                    "unit_of_measurement": "%",
                    "state_class": "measurement",
                    "expected_state": "93",
                },
            ],
        ),
        (
            "54:48:E6:8F:80:A5",
            make_bthome_v2_adv(
                "54:48:E6:8F:80:A5",
                b"\x41\xa4\x72\x66\xc9\x5f\x73\x00\x11\x22\x33\x78\x23\x72\x14",
            ),
            "231d39c1d7cc1ab1aee224cd096db932",
            [
                {
                    "sensor_entity": "sensor.test_device_80a5_temperature",
                    "friendly_name": "Test Device 80A5 Temperature",
                    "unit_of_measurement": "°C",
                    "state_class": "measurement",
                    "expected_state": "25.06",
                },
                {
                    "sensor_entity": "sensor.test_device_80a5_humidity",
                    "friendly_name": "Test Device 80A5 Humidity",
                    "unit_of_measurement": "%",
                    "state_class": "measurement",
                    "expected_state": "50.55",
                },
            ],
        ),
    ],
)
async def test_v2_sensors(
    hass: HomeAssistant,
    mac_address,
    advertisement,
    bind_key,
    result,
) -> None:
    """Test the different BTHome V2 sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=mac_address,
        data={"bindkey": bind_key},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        advertisement,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == len(result)

    for meas in result:
        sensor = hass.states.get(meas["sensor_entity"])
        sensor_attr = sensor.attributes
        assert sensor.state == meas["expected_state"]
        assert sensor_attr[ATTR_FRIENDLY_NAME] == meas["friendly_name"]
        if ATTR_UNIT_OF_MEASUREMENT in sensor_attr:
            # Some sensors don't have a unit of measurement
            assert sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == meas["unit_of_measurement"]
        if ATTR_STATE_CLASS in sensor_attr:
            # Some sensors have state class None
            assert sensor_attr[ATTR_STATE_CLASS] == meas["state_class"]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_unavailable(hass: HomeAssistant) -> None:
    """Test normal device goes to unavailable after 60 minutes."""
    start_monotonic = time.monotonic()

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
        data={},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        make_bthome_v2_adv(
            "A4:C1:38:8D:18:B2",
            b"\x40\x04\x13\x8a\x01",
        ),
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    pressure_sensor = hass.states.get("sensor.test_device_18b2_pressure")

    assert pressure_sensor.state == "1008.83"

    # Fastforward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1

    with patch_bluetooth_time(monotonic_now), patch_all_discovered_devices([]):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
        )
        await hass.async_block_till_done()

    pressure_sensor = hass.states.get("sensor.test_device_18b2_pressure")

    # Normal devices should go to unavailable
    assert pressure_sensor.state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert CONF_SLEEPY_DEVICE not in entry.data


async def test_sleepy_device(hass: HomeAssistant) -> None:
    """Test sleepy device does not go to unavailable after 60 minutes."""
    start_monotonic = time.monotonic()

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
        data={},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        make_bthome_v2_adv(
            "A4:C1:38:8D:18:B2",
            b"\x44\x04\x13\x8a\x01",
        ),
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    pressure_sensor = hass.states.get("sensor.test_device_18b2_pressure")

    assert pressure_sensor.state == "1008.83"

    # Fastforward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1

    with patch_bluetooth_time(monotonic_now), patch_all_discovered_devices([]):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
        )
        await hass.async_block_till_done()

    pressure_sensor = hass.states.get("sensor.test_device_18b2_pressure")

    # Sleepy devices should keep their state over time
    assert pressure_sensor.state == "1008.83"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.data[CONF_SLEEPY_DEVICE] is True


async def test_sleepy_device_restore_state(hass: HomeAssistant) -> None:
    """Test sleepy device does not go to unavailable after 60 minutes and restores state."""
    start_monotonic = time.monotonic()

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
        data={},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        make_bthome_v2_adv(
            "A4:C1:38:8D:18:B2",
            b"\x44\x04\x13\x8a\x01",
        ),
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    pressure_sensor = hass.states.get("sensor.test_device_18b2_pressure")

    assert pressure_sensor.state == "1008.83"

    # Fastforward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1

    with patch_bluetooth_time(monotonic_now), patch_all_discovered_devices([]):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
        )
        await hass.async_block_till_done()

    pressure_sensor = hass.states.get("sensor.test_device_18b2_pressure")

    # Sleepy devices should keep their state over time
    assert pressure_sensor.state == "1008.83"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    pressure_sensor = hass.states.get("sensor.test_device_18b2_pressure")

    # Sleepy devices should keep their state over time and restore it
    assert pressure_sensor.state == "1008.83"

    assert entry.data[CONF_SLEEPY_DEVICE] is True
