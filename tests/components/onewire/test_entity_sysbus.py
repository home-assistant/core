"""Tests for 1-Wire devices connected on SysBus."""
from unittest.mock import PropertyMock, patch

from pi1wire import InvalidCRCException, UnsupportResponseException
import pytest

from homeassistant.components.onewire.const import DEFAULT_SYSBUS_MOUNT_DIR, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import TEMP_CELSIUS
from homeassistant.setup import async_setup_component

from tests.common import mock_registry

MOCK_CONFIG = {
    "sensor": {
        "platform": DOMAIN,
        "mount_dir": DEFAULT_SYSBUS_MOUNT_DIR,
        "names": {
            "10-111111111111": "My DS18B20",
        },
    }
}

MOCK_DEVICE_SENSORS = {
    "00-111111111111": {"sensors": []},
    "10-111111111111": {
        "sensors": [
            {
                "entity_id": "sensor.my_ds18b20_temperature",
                "unique_id": "/sys/bus/w1/devices/10-111111111111/w1_slave",
                "injected_value": 25.123,
                "result": "25.1",
                "unit": TEMP_CELSIUS,
            },
        ]
    },
    "1D-111111111111": {"sensors": []},
    "22-111111111111": {
        "sensors": [
            {
                "entity_id": "sensor.22_111111111111_temperature",
                "unique_id": "/sys/bus/w1/devices/22-111111111111/w1_slave",
                "injected_value": FileNotFoundError,
                "result": "unknown",
                "unit": TEMP_CELSIUS,
            },
        ]
    },
    "28-111111111111": {
        "sensors": [
            {
                "entity_id": "sensor.28_111111111111_temperature",
                "unique_id": "/sys/bus/w1/devices/28-111111111111/w1_slave",
                "injected_value": InvalidCRCException,
                "result": "unknown",
                "unit": TEMP_CELSIUS,
            },
        ]
    },
    "3B-111111111111": {
        "sensors": [
            {
                "entity_id": "sensor.3b_111111111111_temperature",
                "unique_id": "/sys/bus/w1/devices/3B-111111111111/w1_slave",
                "injected_value": 29.993,
                "result": "30.0",
                "unit": TEMP_CELSIUS,
            },
        ]
    },
    "42-111111111111": {
        "sensors": [
            {
                "entity_id": "sensor.42_111111111111_temperature",
                "unique_id": "/sys/bus/w1/devices/42-111111111111/w1_slave",
                "injected_value": UnsupportResponseException,
                "result": "unknown",
                "unit": TEMP_CELSIUS,
            },
        ]
    },
    "EF-111111111111": {
        "sensors": [],
    },
    "EF-111111111112": {
        "sensors": [],
    },
}


@pytest.mark.parametrize("device_id", MOCK_DEVICE_SENSORS.keys())
async def test_onewiredirect_setup_valid_device(hass, device_id):
    """Test that sysbus config entry works correctly."""
    entity_registry = mock_registry(hass)

    read_side_effect = []
    expected_sensors = MOCK_DEVICE_SENSORS[device_id]["sensors"]
    for expected_sensor in expected_sensors:
        read_side_effect.append(expected_sensor["injected_value"])

    with patch(
        "homeassistant.components.onewire.sensor.Pi1Wire"
    ) as mock_pi1wire, patch("pi1wire.OneWire") as mock_owsensor:
        type(mock_owsensor).mac_address = PropertyMock(
            return_value=device_id.replace("-", "")
        )
        mock_owsensor.get_temperature.side_effect = read_side_effect
        mock_pi1wire.return_value.find_all_sensors.return_value = [mock_owsensor]
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
