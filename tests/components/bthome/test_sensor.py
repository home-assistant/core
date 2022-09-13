"""Test the BTHome sensors."""

from unittest.mock import patch

import pytest

from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.bthome.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT

from . import make_advertisement, make_encrypted_advertisement

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "mac_address, advertisement, bind_key, result",
    [
        (
            "A4:C1:38:8D:18:B2",
            make_advertisement(
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
            make_advertisement(
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
            make_advertisement(
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
            make_advertisement(
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
            make_advertisement(
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
            make_advertisement(
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
            make_advertisement(
                "A4:C1:38:8D:18:B2",
                b"\x23\x08\xCA\x06",
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
            make_advertisement(
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
            make_advertisement(
                "A4:C1:38:8D:18:B2",
                b"\x04\n\x13\x8a\x14",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_energy",
                    "friendly_name": "Test Device 18B2 Energy",
                    "unit_of_measurement": "kWh",
                    "state_class": "total_increasing",
                    "expected_state": "1346.067",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_advertisement(
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
            make_advertisement(
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
            make_advertisement(
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
            make_advertisement(
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
            make_advertisement(
                "A4:C1:38:8D:18:B2",
                b"\x03\x133\x01",
            ),
            None,
            [
                {
                    "sensor_entity": "sensor.test_device_18b2_volatile_organic_compounds",
                    "friendly_name": "Test Device 18B2 Volatile Organic Compounds",
                    "unit_of_measurement": "µg/m³",
                    "state_class": "measurement",
                    "expected_state": "307",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_advertisement(
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
            make_encrypted_advertisement(
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
async def test_sensors(
    hass,
    mac_address,
    advertisement,
    bind_key,
    result,
):
    """Test the different measurement sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=mac_address,
        data={"bindkey": bind_key},
    )
    entry.add_to_hass(hass)

    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    saved_callback(
        advertisement,
        BluetoothChange.ADVERTISEMENT,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == len(result)

    for meas in result:
        sensor = hass.states.get(meas["sensor_entity"])
        sensor_attr = sensor.attributes
        assert sensor.state == meas["expected_state"]
        assert sensor_attr[ATTR_FRIENDLY_NAME] == meas["friendly_name"]
        if ATTR_UNIT_OF_MEASUREMENT in sensor_attr:
            # Count sensor does not have a unit of measurement
            assert sensor_attr[ATTR_UNIT_OF_MEASUREMENT] == meas["unit_of_measurement"]
        assert sensor_attr[ATTR_STATE_CLASS] == meas["state_class"]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
