"""Tests for 1-Wire sensor platform."""
from unittest.mock import MagicMock, patch

from pyownet.protocol import Error as ProtocolError
import pytest

from homeassistant.components.onewire.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS, DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_STATE,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant

from . import (
    check_and_enable_disabled_entities,
    check_entities,
    setup_owproxy_mock_devices,
    setup_sysbus_mock_devices,
)
from .const import (
    ATTR_DEVICE_FILE,
    ATTR_DEVICE_INFO,
    ATTR_INJECT_READS,
    ATTR_UNIQUE_ID,
    MOCK_OWPROXY_DEVICES,
    MOCK_SYSBUS_DEVICES,
)

from tests.common import mock_device_registry, mock_registry

MOCK_COUPLERS = {
    key: value for (key, value) in MOCK_OWPROXY_DEVICES.items() if "branches" in value
}


@pytest.fixture(autouse=True)
def override_platforms():
    """Override PLATFORMS."""
    with patch("homeassistant.components.onewire.PLATFORMS", [SENSOR_DOMAIN]):
        yield


@pytest.mark.parametrize("device_id", ["1F.111111111111"], indirect=True)
async def test_sensors_on_owserver_coupler(
    hass: HomeAssistant, config_entry: ConfigEntry, owproxy: MagicMock, device_id: str
):
    """Test for 1-Wire sensors connected to DS2409 coupler."""

    entity_registry = mock_registry(hass)

    mock_coupler = MOCK_COUPLERS[device_id]

    dir_side_effect = []  # List of lists of string
    read_side_effect = []  # List of byte arrays

    dir_side_effect.append([f"/{device_id}/"])  # dir on root
    read_side_effect.append(device_id[0:2].encode())  # read family on root
    if ATTR_INJECT_READS in mock_coupler:
        read_side_effect += mock_coupler[ATTR_INJECT_READS]

    expected_entities = []
    for branch, branch_details in mock_coupler["branches"].items():
        dir_side_effect.append(
            [  # dir on branch
                f"/{device_id}/{branch}/{sub_device_id}/"
                for sub_device_id in branch_details
            ]
        )

        for sub_device_id, sub_device in branch_details.items():
            read_side_effect.append(sub_device_id[0:2].encode())
            if ATTR_INJECT_READS in sub_device:
                read_side_effect.extend(sub_device[ATTR_INJECT_READS])

            expected_entities += sub_device[SENSOR_DOMAIN]
            for expected_entity in sub_device[SENSOR_DOMAIN]:
                read_side_effect.append(expected_entity[ATTR_INJECT_READS])

    # Ensure enough read side effect
    read_side_effect.extend([ProtocolError("Missing injected value")] * 10)
    owproxy.return_value.dir.side_effect = dir_side_effect
    owproxy.return_value.read.side_effect = read_side_effect

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(entity_registry.entities) == len(expected_entities)

    for expected_entity in expected_entities:
        entity_id = expected_entity[ATTR_ENTITY_ID]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == expected_entity[ATTR_UNIQUE_ID]
        state = hass.states.get(entity_id)
        assert state.state == expected_entity[ATTR_STATE]
        for attr in (ATTR_DEVICE_CLASS, ATTR_STATE_CLASS, ATTR_UNIT_OF_MEASUREMENT):
            assert state.attributes.get(attr) == expected_entity.get(attr)
        assert state.attributes[ATTR_DEVICE_FILE] == expected_entity[ATTR_DEVICE_FILE]


async def test_owserver_setup_valid_device(
    hass: HomeAssistant, config_entry: ConfigEntry, owproxy: MagicMock, device_id: str
):
    """Test for 1-Wire device.

    As they would be on a clean setup: all binary-sensors and switches disabled.
    """
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    mock_device = MOCK_OWPROXY_DEVICES[device_id]
    expected_entities = mock_device.get(SENSOR_DOMAIN, [])

    setup_owproxy_mock_devices(owproxy, SENSOR_DOMAIN, [device_id])
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(entity_registry.entities) == len(expected_entities)

    check_and_enable_disabled_entities(entity_registry, expected_entities)

    setup_owproxy_mock_devices(owproxy, SENSOR_DOMAIN, [device_id])
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    if len(expected_entities) > 0:
        device_info = mock_device[ATTR_DEVICE_INFO]
        assert len(device_registry.devices) == 1
        registry_entry = device_registry.async_get_device({(DOMAIN, device_id)})
        assert registry_entry is not None
        assert registry_entry.identifiers == {(DOMAIN, device_id)}
        assert registry_entry.manufacturer == device_info[ATTR_MANUFACTURER]
        assert registry_entry.name == device_info[ATTR_NAME]
        assert registry_entry.model == device_info[ATTR_MODEL]

    check_entities(hass, entity_registry, expected_entities)


@pytest.mark.usefixtures("sysbus")
@pytest.mark.parametrize("device_id", MOCK_SYSBUS_DEVICES.keys(), indirect=True)
async def test_onewiredirect_setup_valid_device(
    hass: HomeAssistant, sysbus_config_entry: ConfigEntry, device_id: str
):
    """Test that sysbus config entry works correctly."""

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
        await hass.config_entries.async_setup(sysbus_config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == len(expected_entities)

    if len(expected_entities) > 0:
        device_info = mock_device[ATTR_DEVICE_INFO]
        assert len(device_registry.devices) == 1
        registry_entry = device_registry.async_get_device({(DOMAIN, device_id)})
        assert registry_entry is not None
        assert registry_entry.identifiers == {(DOMAIN, device_id)}
        assert registry_entry.manufacturer == device_info[ATTR_MANUFACTURER]
        assert registry_entry.name == device_info[ATTR_NAME]
        assert registry_entry.model == device_info[ATTR_MODEL]

    check_entities(hass, entity_registry, expected_entities)
