"""Tests for 1-Wire devices connected on OWServer."""
import copy
from unittest.mock import patch

from pyownet.protocol import Error as ProtocolError
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.onewire.binary_sensor import DEVICE_BINARY_SENSORS
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from . import setup_onewire_patched_owserver_integration

from tests.common import mock_registry

MOCK_DEVICE_SENSORS = {
    "12.111111111111": {
        "inject_reads": [
            b"DS2406",  # read device type
        ],
        BINARY_SENSOR_DOMAIN: [
            {
                "entity_id": "binary_sensor.12_111111111111_sensed_a",
                "injected_value": b"    1",
                "result": STATE_ON,
            },
            {
                "entity_id": "binary_sensor.12_111111111111_sensed_b",
                "injected_value": b"    0",
                "result": STATE_OFF,
            },
        ],
    },
}


@pytest.mark.parametrize("device_id", MOCK_DEVICE_SENSORS.keys())
@patch("homeassistant.components.onewire.onewirehub.protocol.proxy")
async def test_owserver_binary_sensor(owproxy, hass, device_id):
    """Test for 1-Wire binary sensor.

    This test forces all entities to be enabled.
    """
    await async_setup_component(hass, "persistent_notification", {})
    entity_registry = mock_registry(hass)

    mock_device_sensor = MOCK_DEVICE_SENSORS[device_id]

    device_family = device_id[0:2]
    dir_return_value = [f"/{device_id}/"]
    read_side_effect = [device_family.encode()]
    if "inject_reads" in mock_device_sensor:
        read_side_effect += mock_device_sensor["inject_reads"]

    expected_sensors = mock_device_sensor[BINARY_SENSOR_DOMAIN]
    for expected_sensor in expected_sensors:
        read_side_effect.append(expected_sensor["injected_value"])

    # Ensure enough read side effect
    read_side_effect.extend([ProtocolError("Missing injected value")] * 10)
    owproxy.return_value.dir.return_value = dir_return_value
    owproxy.return_value.read.side_effect = read_side_effect

    # Force enable binary sensors
    patch_device_binary_sensors = copy.deepcopy(DEVICE_BINARY_SENSORS)
    for item in patch_device_binary_sensors[device_family]:
        item["default_disabled"] = False

    with patch(
        "homeassistant.components.onewire.SUPPORTED_PLATFORMS", [BINARY_SENSOR_DOMAIN]
    ), patch.dict(
        "homeassistant.components.onewire.binary_sensor.DEVICE_BINARY_SENSORS",
        patch_device_binary_sensors,
    ):
        await setup_onewire_patched_owserver_integration(hass)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == len(expected_sensors)

    for expected_sensor in expected_sensors:
        entity_id = expected_sensor["entity_id"]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        state = hass.states.get(entity_id)
        assert state.state == expected_sensor["result"]
        assert state.attributes["device_file"] == expected_sensor.get(
            "device_file", registry_entry.unique_id
        )
