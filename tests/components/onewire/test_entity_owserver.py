"""Tests for 1-Wire devices connected on OWServer."""
from unittest.mock import patch

from pyownet.protocol import Error as ProtocolError
import pytest

from homeassistant.components.onewire.const import (
    DEFAULT_OWSERVER_PORT,
    DOMAIN,
    PRESSURE_CBAR,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.setup import async_setup_component

from tests.common import mock_registry

MOCK_CONFIG = {
    "sensor": {
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
            },
            {
                "entity_id": "sensor.1d_111111111111_counter_b",
                "unique_id": "/1D.111111111111/counter.B",
                "injected_value": b"    248125",
                "result": "248125",
                "unit": "count",
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
            },
            {
                "entity_id": "sensor.ef_111111111111_humidity_raw",
                "unique_id": "/EF.111111111111/humidity/humidity_raw",
                "injected_value": b"    65.541",
                "result": "65.5",
                "unit": PERCENTAGE,
            },
            {
                "entity_id": "sensor.ef_111111111111_temperature",
                "unique_id": "/EF.111111111111/humidity/temperature",
                "injected_value": b"    25.123",
                "result": "25.1",
                "unit": TEMP_CELSIUS,
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
            },
            {
                "entity_id": "sensor.ef_111111111112_wetness_1",
                "unique_id": "/EF.111111111112/moisture/sensor.1",
                "injected_value": b"    42.541",
                "result": "42.5",
                "unit": PERCENTAGE,
            },
            {
                "entity_id": "sensor.ef_111111111112_moisture_2",
                "unique_id": "/EF.111111111112/moisture/sensor.2",
                "injected_value": b"    43.123",
                "result": "43.1",
                "unit": PRESSURE_CBAR,
            },
            {
                "entity_id": "sensor.ef_111111111112_moisture_3",
                "unique_id": "/EF.111111111112/moisture/sensor.3",
                "injected_value": b"    44.123",
                "result": "44.1",
                "unit": PRESSURE_CBAR,
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
        state = hass.states.get(entity_id)
        assert state.state == expected_sensor["result"]
