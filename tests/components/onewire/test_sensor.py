"""Tests for 1-Wire sensor platform."""
from unittest.mock import patch

from pyownet.protocol import Error as ProtocolError
import pytest

from homeassistant.components.onewire.const import (
    DEFAULT_SYSBUS_MOUNT_DIR,
    DOMAIN,
    PLATFORMS,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.setup import async_setup_component

from . import (
    setup_onewire_patched_owserver_integration,
    setup_onewire_sysbus_integration,
    setup_owproxy_mock_devices,
    setup_sysbus_mock_devices,
)
from .const import MOCK_OWPROXY_DEVICES, MOCK_SYSBUS_DEVICES

from tests.common import assert_setup_component, mock_device_registry, mock_registry

MOCK_COUPLERS = {
    key: value for (key, value) in MOCK_OWPROXY_DEVICES.items() if "branches" in value
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

    with patch("homeassistant.components.onewire.PLATFORMS", [SENSOR_DOMAIN]):
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


@pytest.mark.parametrize("device_id", MOCK_OWPROXY_DEVICES.keys())
@pytest.mark.parametrize("platform", PLATFORMS)
@patch("homeassistant.components.onewire.onewirehub.protocol.proxy")
async def test_owserver_setup_valid_device(owproxy, hass, device_id, platform):
    """Test for 1-Wire device.

    As they would be on a clean setup: all binary-sensors and switches disabled.
    """
    await async_setup_component(hass, "persistent_notification", {})
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    setup_owproxy_mock_devices(owproxy, platform, [device_id])

    mock_device = MOCK_OWPROXY_DEVICES[device_id]
    expected_entities = mock_device.get(platform, [])

    with patch("homeassistant.components.onewire.PLATFORMS", [platform]):
        await setup_onewire_patched_owserver_integration(hass)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == len(expected_entities)

    if len(expected_entities) > 0:
        device_info = mock_device["device_info"]
        assert len(device_registry.devices) == 1
        registry_entry = device_registry.async_get_device({(DOMAIN, device_id)})
        assert registry_entry is not None
        assert registry_entry.identifiers == {(DOMAIN, device_id)}
        assert registry_entry.manufacturer == device_info["manufacturer"]
        assert registry_entry.name == device_info["name"]
        assert registry_entry.model == device_info["model"]

    for expected_entity in expected_entities:
        entity_id = expected_entity["entity_id"]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == expected_entity["unique_id"]
        assert registry_entry.unit_of_measurement == expected_entity["unit"]
        assert registry_entry.device_class == expected_entity["class"]
        assert registry_entry.disabled == expected_entity.get("disabled", False)
        state = hass.states.get(entity_id)
        if registry_entry.disabled:
            assert state is None
        else:
            assert state.state == expected_entity["result"]
            assert state.attributes["device_file"] == expected_entity.get(
                "device_file", registry_entry.unique_id
            )


@pytest.mark.parametrize("device_id", MOCK_SYSBUS_DEVICES.keys())
async def test_onewiredirect_setup_valid_device(hass, device_id):
    """Test that sysbus config entry works correctly."""
    await async_setup_component(hass, "persistent_notification", {})
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    glob_result, read_side_effect = setup_sysbus_mock_devices(
        SENSOR_DOMAIN, [device_id]
    )

    mock_device = MOCK_SYSBUS_DEVICES[device_id]
    expected_entities = mock_device.get(SENSOR_DOMAIN, [])

    with patch("pi1wire._finder.glob.glob", return_value=glob_result,), patch(
        "pi1wire.OneWire.get_temperature",
        side_effect=read_side_effect,
    ):
        assert await setup_onewire_sysbus_integration(hass)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == len(expected_entities)

    if len(expected_entities) > 0:
        device_info = mock_device["device_info"]
        assert len(device_registry.devices) == 1
        registry_entry = device_registry.async_get_device({(DOMAIN, device_id)})
        assert registry_entry is not None
        assert registry_entry.identifiers == {(DOMAIN, device_id)}
        assert registry_entry.manufacturer == device_info["manufacturer"]
        assert registry_entry.name == device_info["name"]
        assert registry_entry.model == device_info["model"]

    for expected_sensor in expected_entities:
        entity_id = expected_sensor["entity_id"]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == expected_sensor["unique_id"]
        assert registry_entry.unit_of_measurement == expected_sensor["unit"]
        assert registry_entry.device_class == expected_sensor["class"]
        state = hass.states.get(entity_id)
        assert state.state == expected_sensor["result"]
