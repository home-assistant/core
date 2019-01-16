"""
Test for the SmartThings switch platform.

The only mocking required is of the underlying SmartThings API object so
real HTTP calls are not initiated during testing.
"""
from unittest.mock import Mock

from pysmartthings import DeviceEntity
from pysmartthings.api import Api
import pytest

from homeassistant.components.smartthings import DeviceBroker
from homeassistant.components.smartthings.const import (
    DATA_BROKERS, DOMAIN as SMARTTHINGS_DOMAIN, SIGNAL_SMARTTHINGS_UPDATE)
from homeassistant.components.switch import smartthings
from homeassistant.config_entries import (
    CONN_CLASS_CLOUD_PUSH, SOURCE_USER, ConfigEntry)
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import mock_coro

DEVICE_DATA = {
    "deviceId": "a367d7df-39d8-4aa4-84e2-2596e5b02138",
    "name": "GE In-Wall Smart Switch",
    "label": "Switch 1",
    "deviceManufacturerCode": "9135fc86-0929-4436-bf73-5d75f523d9db",
    "locationId": "fcd829e9-82f4-45b9-acfd-62fda029af80",
    "components": [
        {
            "id": "main",
            "capabilities": [
                {
                    "id": "switch",
                    "version": 1
                }
            ]
        }
    ],
    "dth": {
        "deviceTypeId": "b678b29d-2726-4e4f-9c3f-7aa05bd08964",
        "deviceTypeName": "Switch",
        "deviceNetworkType": "ZWAVE"
    },
    "type": "DTH"
}


@pytest.fixture(name="device_factory")
def create_device_fixture():
    """Fixture that creates SmartThings Devices."""
    api = Mock(spec=Api)
    api.post_device_command.return_value = mock_coro(return_value={})

    def _factory(initial_state: bool = True):
        device = DeviceEntity(api, data=DEVICE_DATA)
        device.status.apply_data({
            "components": {
                "main": {
                    "switch": {
                        "switch": {
                            "value": "on" if initial_state else "off"
                        }
                    }
                }
            }
        })
        return device
    return _factory


async def _setup_platform(hass, *devices):
    """Set up the SmartThings switch platform and prerequisites."""
    hass.config.components.add(SMARTTHINGS_DOMAIN)
    broker = DeviceBroker(hass, devices, '')
    config_entry = ConfigEntry("1", SMARTTHINGS_DOMAIN, "Test", {},
                               SOURCE_USER, CONN_CLASS_CLOUD_PUSH)
    hass.data[SMARTTHINGS_DOMAIN] = {
        DATA_BROKERS: {
            config_entry.entry_id: broker
        }
    }
    await hass.config_entries.async_forward_entry_setup(config_entry, 'switch')
    await hass.async_block_till_done()
    return config_entry


async def test_async_setup_platform():
    """Test setup platform does nothing (it uses config entries)."""
    await smartthings.async_setup_platform(None, None, None)


async def test_entity_attributes(hass, device_factory):
    """Test the attributes of the entity are correct."""
    # Arrange
    device = device_factory()
    # Act
    await _setup_platform(hass, device)
    # Assert
    component = hass.data['switch']
    entity = component.get_entity('switch.switch_1')
    assert entity.unique_id == device.device_id
    assert entity.name == device.label
    assert not entity.should_poll
    assert entity.device_info == {
        'identifiers': {
            (SMARTTHINGS_DOMAIN, device.device_id)
        },
        'name': device.label,
        'model': device.device_type_name,
        'manufacturer': 'SmartThings'
    }


async def test_turn_off(hass, device_factory):
    """Test the switch turns of successfully."""
    # Arrange
    await _setup_platform(hass, device_factory())
    # Act
    await hass.services.async_call(
        'switch', 'turn_off', {'entity_id': 'switch.switch_1'},
        blocking=True)
    # Assert
    switch = hass.states.get('switch.switch_1')
    assert switch is not None
    assert switch.state == 'off'


async def test_turn_on(hass, device_factory):
    """Test the switch turns of successfully."""
    # Arrange
    await _setup_platform(hass, device_factory(False))
    # Act
    await hass.services.async_call(
        'switch', 'turn_on', {'entity_id': 'switch.switch_1'},
        blocking=True)
    # Assert
    switch = hass.states.get('switch.switch_1')
    assert switch is not None
    assert switch.state == 'on'


async def test_update_from_signal(hass, device_factory):
    """Test the switch updates when receiving a signal."""
    # Arrange
    device = device_factory(False)
    await _setup_platform(hass, device)
    await device.switch_on(True)
    # Act
    async_dispatcher_send(hass, SIGNAL_SMARTTHINGS_UPDATE, [device.device_id])
    # Assert
    await hass.async_block_till_done()
    switch = hass.states.get('switch.switch_1')
    assert switch is not None
    assert switch.state == 'on'


async def test_unload_config_entry(hass, device_factory):
    """Test the switch is removed when the config entry is unloaded."""
    # Arrange
    config_entry = await _setup_platform(hass, device_factory())
    # Act
    await hass.config_entries.async_forward_entry_unload(
        config_entry, 'switch')
    # Assert
    assert not hass.states.get('switch.switch_1')
