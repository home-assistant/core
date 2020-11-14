"""Tests for 1-Wire devices connected on OWServer."""
from pyownet.protocol import Error as ProtocolError
import pytest

from homeassistant.components.onewire.const import (
    DEFAULT_OWSERVER_PORT,
    DOMAIN,
    PRESSURE_CBAR,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRICAL_CURRENT_AMPERE,
    LIGHT_LUX,
    PERCENTAGE,
    PRESSURE_MBAR,
    TEMP_CELSIUS,
    VOLT,
)
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import mock_registry

MOCK_CONFIG = {
    SENSOR_DOMAIN: {
        "platform": DOMAIN,
        "host": "localhost",
        "port": DEFAULT_OWSERVER_PORT,
        "names": {
            "10.111111111111": "My DS18B20",
        },
    }
}

MOCK_DEVICE_SENSORS = {
    "00.111111111111": {"sensors": []},
    "10.111111111111": {
        "sensors": [
            {
                "entity_id": "sensor.my_ds18b20_temperature",
                "unique_id": "/10.111111111111/temperature",
                "injected_value": b"    25.123",
                "result": "25.1",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ]
    },
    "12.111111111111": {
        "sensors": [
            {
                "entity_id": "sensor.12_111111111111_temperature",
                "unique_id": "/12.111111111111/TAI8570/temperature",
                "injected_value": b"    25.123",
                "result": "25.1",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
            {
                "entity_id": "sensor.12_111111111111_pressure",
                "unique_id": "/12.111111111111/TAI8570/pressure",
                "injected_value": b"  1025.123",
                "result": "1025.1",
                "unit": PRESSURE_MBAR,
                "class": DEVICE_CLASS_PRESSURE,
            },
        ]
    },
    "1D.111111111111": {
        "sensors": [
            {
                "entity_id": "sensor.1d_111111111111_counter_a",
                "unique_id": "/1D.111111111111/counter.A",
                "injected_value": b"    251123",
                "result": "251123",
                "unit": "count",
                "class": None,
            },
            {
                "entity_id": "sensor.1d_111111111111_counter_b",
                "unique_id": "/1D.111111111111/counter.B",
                "injected_value": b"    248125",
                "result": "248125",
                "unit": "count",
                "class": None,
            },
        ]
    },
    "22.111111111111": {
        "sensors": [
            {
                "entity_id": "sensor.22_111111111111_temperature",
                "unique_id": "/22.111111111111/temperature",
                "injected_value": ProtocolError,
                "result": "unknown",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ]
    },
    "26.111111111111": {
        "sensors": [
            {
                "entity_id": "sensor.26_111111111111_temperature",
                "unique_id": "/26.111111111111/temperature",
                "injected_value": b"    25.123",
                "result": "25.1",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
            {
                "entity_id": "sensor.26_111111111111_humidity",
                "unique_id": "/26.111111111111/humidity",
                "injected_value": b"    72.7563",
                "result": "72.8",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
            },
            {
                "entity_id": "sensor.26_111111111111_humidity_hih3600",
                "unique_id": "/26.111111111111/HIH3600/humidity",
                "injected_value": b"    73.7563",
                "result": "73.8",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
            },
            {
                "entity_id": "sensor.26_111111111111_humidity_hih4000",
                "unique_id": "/26.111111111111/HIH4000/humidity",
                "injected_value": b"    74.7563",
                "result": "74.8",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
            },
            {
                "entity_id": "sensor.26_111111111111_humidity_hih5030",
                "unique_id": "/26.111111111111/HIH5030/humidity",
                "injected_value": b"    75.7563",
                "result": "75.8",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
            },
            {
                "entity_id": "sensor.26_111111111111_humidity_htm1735",
                "unique_id": "/26.111111111111/HTM1735/humidity",
                "injected_value": ProtocolError,
                "result": "unknown",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
            },
            {
                "entity_id": "sensor.26_111111111111_pressure",
                "unique_id": "/26.111111111111/B1-R1-A/pressure",
                "injected_value": b"    969.265",
                "result": "969.3",
                "unit": PRESSURE_MBAR,
                "class": DEVICE_CLASS_PRESSURE,
            },
            {
                "entity_id": "sensor.26_111111111111_illuminance",
                "unique_id": "/26.111111111111/S3-R1-A/illuminance",
                "injected_value": b"    65.8839",
                "result": "65.9",
                "unit": LIGHT_LUX,
                "class": DEVICE_CLASS_ILLUMINANCE,
            },
            {
                "entity_id": "sensor.26_111111111111_voltage_vad",
                "unique_id": "/26.111111111111/VAD",
                "injected_value": b"     2.97",
                "result": "3.0",
                "unit": VOLT,
                "class": DEVICE_CLASS_VOLTAGE,
            },
            {
                "entity_id": "sensor.26_111111111111_voltage_vdd",
                "unique_id": "/26.111111111111/VDD",
                "injected_value": b"    4.74",
                "result": "4.7",
                "unit": VOLT,
                "class": DEVICE_CLASS_VOLTAGE,
            },
            {
                "entity_id": "sensor.26_111111111111_current",
                "unique_id": "/26.111111111111/IAD",
                "injected_value": b"       1",
                "result": "1.0",
                "unit": ELECTRICAL_CURRENT_AMPERE,
                "class": DEVICE_CLASS_CURRENT,
            },
        ]
    },
    "28.111111111111": {
        "sensors": [
            {
                "entity_id": "sensor.28_111111111111_temperature",
                "unique_id": "/28.111111111111/temperature",
                "injected_value": b"    26.984",
                "result": "27.0",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ]
    },
    "3B.111111111111": {
        "sensors": [
            {
                "entity_id": "sensor.3b_111111111111_temperature",
                "unique_id": "/3B.111111111111/temperature",
                "injected_value": b"    28.243",
                "result": "28.2",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ]
    },
    "42.111111111111": {
        "sensors": [
            {
                "entity_id": "sensor.42_111111111111_temperature",
                "unique_id": "/42.111111111111/temperature",
                "injected_value": b"    29.123",
                "result": "29.1",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ]
    },
    "EF.111111111111": {
        "inject_reads": [
            b"HobbyBoards_EF",  # read type
        ],
        "sensors": [
            {
                "entity_id": "sensor.ef_111111111111_humidity",
                "unique_id": "/EF.111111111111/humidity/humidity_corrected",
                "injected_value": b"    67.745",
                "result": "67.7",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
            },
            {
                "entity_id": "sensor.ef_111111111111_humidity_raw",
                "unique_id": "/EF.111111111111/humidity/humidity_raw",
                "injected_value": b"    65.541",
                "result": "65.5",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
            },
            {
                "entity_id": "sensor.ef_111111111111_temperature",
                "unique_id": "/EF.111111111111/humidity/temperature",
                "injected_value": b"    25.123",
                "result": "25.1",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
    },
    "EF.111111111112": {
        "inject_reads": [
            b"HB_MOISTURE_METER",  # read type
            b"         1",  # read is_leaf_0
            b"         1",  # read is_leaf_1
            b"         0",  # read is_leaf_2
            b"         0",  # read is_leaf_3
        ],
        "sensors": [
            {
                "entity_id": "sensor.ef_111111111112_wetness_0",
                "unique_id": "/EF.111111111112/moisture/sensor.0",
                "injected_value": b"    41.745",
                "result": "41.7",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
            },
            {
                "entity_id": "sensor.ef_111111111112_wetness_1",
                "unique_id": "/EF.111111111112/moisture/sensor.1",
                "injected_value": b"    42.541",
                "result": "42.5",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_HUMIDITY,
            },
            {
                "entity_id": "sensor.ef_111111111112_moisture_2",
                "unique_id": "/EF.111111111112/moisture/sensor.2",
                "injected_value": b"    43.123",
                "result": "43.1",
                "unit": PRESSURE_CBAR,
                "class": DEVICE_CLASS_PRESSURE,
            },
            {
                "entity_id": "sensor.ef_111111111112_moisture_3",
                "unique_id": "/EF.111111111112/moisture/sensor.3",
                "injected_value": b"    44.123",
                "result": "44.1",
                "unit": PRESSURE_CBAR,
                "class": DEVICE_CLASS_PRESSURE,
            },
        ],
    },
}


@pytest.mark.parametrize("device_id", MOCK_DEVICE_SENSORS.keys())
async def test_owserver_setup_valid_device(hass, device_id):
    """Test for 1-Wire device."""
    entity_registry = mock_registry(hass)

    dir_return_value = [f"/{device_id}/"]
    read_side_effect = [device_id[0:2].encode()]
    if "inject_reads" in MOCK_DEVICE_SENSORS[device_id]:
        read_side_effect += MOCK_DEVICE_SENSORS[device_id]["inject_reads"]

    expected_sensors = MOCK_DEVICE_SENSORS[device_id]["sensors"]
    for expected_sensor in expected_sensors:
        read_side_effect.append(expected_sensor["injected_value"])

    # Ensure enough read side effect
    read_side_effect.extend([ProtocolError("Missing injected value")] * 10)

    with patch("homeassistant.components.onewire.sensor.protocol.proxy") as owproxy:
        owproxy.return_value.dir.return_value = dir_return_value
        owproxy.return_value.read.side_effect = read_side_effect

        assert await async_setup_component(hass, SENSOR_DOMAIN, MOCK_CONFIG)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == len(expected_sensors)

    for expected_sensor in expected_sensors:
        entity_id = expected_sensor["entity_id"]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == expected_sensor["unique_id"]
        assert registry_entry.unit_of_measurement == expected_sensor["unit"]
        assert registry_entry.device_class == expected_sensor["class"]
        state = hass.states.get(entity_id)
        assert state.state == expected_sensor["result"]
