"""Tests for 1-Wire sensor platform."""
from unittest.mock import patch

from pyownet.protocol import Error as ProtocolError
import pytest

from homeassistant.components.onewire.const import DEFAULT_SYSBUS_MOUNT_DIR, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.setup import async_setup_component

from . import setup_onewire_patched_owserver_integration

from tests.common import assert_setup_component, mock_registry

MOCK_COUPLERS = {
    "1F.111111111111": {
        "inject_reads": [
            b"DS2409",  # read device type
        ],
        "branches": {
            "aux": {},
            "main": {
                "1D.111111111111": {
                    "inject_reads": [
                        b"DS2423",  # read device type
                    ],
                    "device_info": {
                        "identifiers": {(DOMAIN, "1D.111111111111")},
                        "manufacturer": "Maxim Integrated",
                        "model": "DS2423",
                        "name": "1D.111111111111",
                    },
                    SENSOR_DOMAIN: [
                        {
                            "entity_id": "sensor.1d_111111111111_counter_a",
                            "device_file": "/1F.111111111111/main/1D.111111111111/counter.A",
                            "unique_id": "/1D.111111111111/counter.A",
                            "injected_value": b"    251123",
                            "result": "251123",
                            "unit": "count",
                            "class": None,
                        },
                        {
                            "entity_id": "sensor.1d_111111111111_counter_b",
                            "device_file": "/1F.111111111111/main/1D.111111111111/counter.B",
                            "unique_id": "/1D.111111111111/counter.B",
                            "injected_value": b"    248125",
                            "result": "248125",
                            "unit": "count",
                            "class": None,
                        },
                    ],
                },
            },
        },
    }
}


async def test_setup_minimum(hass):
    """Test old platform setup with minimum configuration."""
    config = {"sensor": {"platform": "onewire"}}
    with assert_setup_component(1, "sensor"):
        assert await async_setup_component(hass, SENSOR_DOMAIN, config)
    await hass.async_block_till_done()


async def test_setup_sysbus(hass):
    """Test old platform setup with SysBus configuration."""
    config = {
        "sensor": {
            "platform": "onewire",
            "mount_dir": DEFAULT_SYSBUS_MOUNT_DIR,
        }
    }
    with assert_setup_component(1, "sensor"):
        assert await async_setup_component(hass, SENSOR_DOMAIN, config)
    await hass.async_block_till_done()


async def test_setup_owserver(hass):
    """Test old platform setup with OWServer configuration."""
    config = {"sensor": {"platform": "onewire", "host": "localhost"}}
    with assert_setup_component(1, "sensor"):
        assert await async_setup_component(hass, SENSOR_DOMAIN, config)
    await hass.async_block_till_done()


async def test_setup_owserver_with_port(hass):
    """Test old platform setup with OWServer configuration."""
    config = {"sensor": {"platform": "onewire", "host": "localhost", "port": "1234"}}
    with assert_setup_component(1, "sensor"):
        assert await async_setup_component(hass, SENSOR_DOMAIN, config)
    await hass.async_block_till_done()


@pytest.mark.parametrize("device_id", ["1F.111111111111"])
@patch("homeassistant.components.onewire.onewirehub.protocol.proxy")
async def test_sensors_on_owserver_coupler(owproxy, hass, device_id):
    """Test for 1-Wire sensors connected to DS2409 coupler."""
    await async_setup_component(hass, "persistent_notification", {})
    entity_registry = mock_registry(hass)

    mock_coupler = MOCK_COUPLERS[device_id]

    dir_side_effect = []  # List of lists of string
    read_side_effect = []  # List of byte arrays

    dir_side_effect.append([f"/{device_id}/"])  # dir on root
    read_side_effect.append(device_id[0:2].encode())  # read family on root
    if "inject_reads" in mock_coupler:
        read_side_effect += mock_coupler["inject_reads"]

    expected_sensors = []
    for branch, branch_details in mock_coupler["branches"].items():
        dir_side_effect.append(
            [  # dir on branch
                f"/{device_id}/{branch}/{sub_device_id}/"
                for sub_device_id in branch_details
            ]
        )

        for sub_device_id, sub_device in branch_details.items():
            read_side_effect.append(sub_device_id[0:2].encode())
            if "inject_reads" in sub_device:
                read_side_effect.extend(sub_device["inject_reads"])

            expected_sensors += sub_device[SENSOR_DOMAIN]
            for expected_sensor in sub_device[SENSOR_DOMAIN]:
                read_side_effect.append(expected_sensor["injected_value"])

    # Ensure enough read side effect
    read_side_effect.extend([ProtocolError("Missing injected value")] * 10)
    owproxy.return_value.dir.side_effect = dir_side_effect
    owproxy.return_value.read.side_effect = read_side_effect

    with patch("homeassistant.components.onewire.SUPPORTED_PLATFORMS", [SENSOR_DOMAIN]):
        await setup_onewire_patched_owserver_integration(hass)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == len(expected_sensors)

    for expected_sensor in expected_sensors:
        entity_id = expected_sensor["entity_id"]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == expected_sensor["unique_id"]
        assert registry_entry.unit_of_measurement == expected_sensor["unit"]
        assert registry_entry.device_class == expected_sensor["class"]
        assert registry_entry.disabled == expected_sensor.get("disabled", False)
        state = hass.states.get(entity_id)
        if registry_entry.disabled:
            assert state is None
        else:
            assert state.state == expected_sensor["result"]
        assert state.attributes["device_file"] == expected_sensor["device_file"]
