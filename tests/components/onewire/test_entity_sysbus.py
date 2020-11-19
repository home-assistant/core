"""Tests for 1-Wire devices connected on SysBus."""
from pi1wire import InvalidCRCException, UnsupportResponseException
import pytest

from homeassistant.components.onewire.const import DEFAULT_SYSBUS_MOUNT_DIR, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import mock_device_registry, mock_registry

MOCK_CONFIG = {
    SENSOR_DOMAIN: {
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
        "device_info": {
            "identifiers": {(DOMAIN, "10-111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "10",
            "name": "10-111111111111",
        },
        "sensors": [
            {
                "entity_id": "sensor.my_ds18b20_temperature",
                "unique_id": "/sys/bus/w1/devices/10-111111111111/w1_slave",
                "injected_value": 25.123,
                "result": "25.1",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
    },
    "12-111111111111": {"sensors": []},
    "1D-111111111111": {"sensors": []},
    "22-111111111111": {
        "device_info": {
            "identifiers": {(DOMAIN, "22-111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "22",
            "name": "22-111111111111",
        },
        "sensors": [
            {
                "entity_id": "sensor.22_111111111111_temperature",
                "unique_id": "/sys/bus/w1/devices/22-111111111111/w1_slave",
                "injected_value": FileNotFoundError,
                "result": "unknown",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
    },
    "26-111111111111": {"sensors": []},
    "28-111111111111": {
        "device_info": {
            "identifiers": {(DOMAIN, "28-111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "28",
            "name": "28-111111111111",
        },
        "sensors": [
            {
                "entity_id": "sensor.28_111111111111_temperature",
                "unique_id": "/sys/bus/w1/devices/28-111111111111/w1_slave",
                "injected_value": InvalidCRCException,
                "result": "unknown",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
    },
    "29-111111111111": {"sensors": []},
    "3B-111111111111": {
        "device_info": {
            "identifiers": {(DOMAIN, "3B-111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "3B",
            "name": "3B-111111111111",
        },
        "sensors": [
            {
                "entity_id": "sensor.3b_111111111111_temperature",
                "unique_id": "/sys/bus/w1/devices/3B-111111111111/w1_slave",
                "injected_value": 29.993,
                "result": "30.0",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
    },
    "42-111111111111": {
        "device_info": {
            "identifiers": {(DOMAIN, "42-111111111111")},
            "manufacturer": "Maxim Integrated",
            "model": "42",
            "name": "42-111111111111",
        },
        "sensors": [
            {
                "entity_id": "sensor.42_111111111111_temperature",
                "unique_id": "/sys/bus/w1/devices/42-111111111111/w1_slave",
                "injected_value": UnsupportResponseException,
                "result": "unknown",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
        ],
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
    device_registry = mock_device_registry(hass)

    mock_device_sensor = MOCK_DEVICE_SENSORS[device_id]

    glob_result = [f"/{DEFAULT_SYSBUS_MOUNT_DIR}/{device_id}"]
    read_side_effect = []
    expected_sensors = mock_device_sensor["sensors"]
    for expected_sensor in expected_sensors:
        read_side_effect.append(expected_sensor["injected_value"])

    # Ensure enough read side effect
    read_side_effect.extend([FileNotFoundError("Missing injected value")] * 20)

    with patch(
        "homeassistant.components.onewire.onewirehub.os.path.isdir", return_value=True
    ), patch("pi1wire._finder.glob.glob", return_value=glob_result,), patch(
        "pi1wire.OneWire.get_temperature",
        side_effect=read_side_effect,
    ):
        assert await async_setup_component(hass, SENSOR_DOMAIN, MOCK_CONFIG)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == len(expected_sensors)

    if len(expected_sensors) > 0:
        device_info = mock_device_sensor["device_info"]
        assert len(device_registry.devices) == 1
        registry_entry = device_registry.async_get_device({(DOMAIN, device_id)}, set())
        assert registry_entry is not None
        assert registry_entry.identifiers == {(DOMAIN, device_id)}
        assert registry_entry.manufacturer == device_info["manufacturer"]
        assert registry_entry.name == device_info["name"]
        assert registry_entry.model == device_info["model"]

    for expected_sensor in expected_sensors:
        entity_id = expected_sensor["entity_id"]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == expected_sensor["unique_id"]
        assert registry_entry.unit_of_measurement == expected_sensor["unit"]
        assert registry_entry.device_class == expected_sensor["class"]
        state = hass.states.get(entity_id)
        assert state.state == expected_sensor["result"]
