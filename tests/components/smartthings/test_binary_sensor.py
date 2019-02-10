"""
Test for the SmartThings binary_sensor platform.

The only mocking required is of the underlying SmartThings API object so
real HTTP calls are not initiated during testing.
"""
from pysmartthings import ATTRIBUTES, CAPABILITIES, Attribute, Capability

from homeassistant.components.binary_sensor import DEVICE_CLASSES
from homeassistant.components.smartthings import DeviceBroker, binary_sensor
from homeassistant.components.smartthings.const import (
    DATA_BROKERS, DOMAIN, SIGNAL_SMARTTHINGS_UPDATE)
from homeassistant.config_entries import (
    CONN_CLASS_CLOUD_PUSH, SOURCE_USER, ConfigEntry)
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.helpers.dispatcher import async_dispatcher_send


async def _setup_platform(hass, *devices):
    """Set up the SmartThings binary_sensor platform and prerequisites."""
    hass.config.components.add(DOMAIN)
    broker = DeviceBroker(hass, devices, '')
    config_entry = ConfigEntry("1", DOMAIN, "Test", {},
                               SOURCE_USER, CONN_CLASS_CLOUD_PUSH)
    hass.data[DOMAIN] = {
        DATA_BROKERS: {
            config_entry.entry_id: broker
        }
    }
    await hass.config_entries.async_forward_entry_setup(
        config_entry, 'binary_sensor')
    await hass.async_block_till_done()
    return config_entry


async def test_mapping_integrity():
    """Test ensures the map dicts have proper integrity."""
    # Ensure every CAPABILITY_TO_ATTRIB key is in CAPABILITIES
    # Ensure every CAPABILITY_TO_ATTRIB value is in ATTRIB_TO_CLASS keys
    for capability, attrib in binary_sensor.CAPABILITY_TO_ATTRIB.items():
        assert capability in CAPABILITIES, capability
        assert attrib in ATTRIBUTES, attrib
        assert attrib in binary_sensor.ATTRIB_TO_CLASS.keys(), attrib
    # Ensure every ATTRIB_TO_CLASS value is in DEVICE_CLASSES
    for attrib, device_class in binary_sensor.ATTRIB_TO_CLASS.items():
        assert attrib in ATTRIBUTES, attrib
        assert device_class in DEVICE_CLASSES, device_class


async def test_async_setup_platform():
    """Test setup platform does nothing (it uses config entries)."""
    await binary_sensor.async_setup_platform(None, None, None)


async def test_entity_state(hass, device_factory):
    """Tests the state attributes properly match the light types."""
    device = device_factory('Motion Sensor 1', [Capability.motion_sensor],
                            {Attribute.motion: 'inactive'})
    await _setup_platform(hass, device)
    state = hass.states.get('binary_sensor.motion_sensor_1_motion')
    assert state.state == 'off'
    assert state.attributes[ATTR_FRIENDLY_NAME] ==\
        device.label + ' ' + Attribute.motion


async def test_entity_and_device_attributes(hass, device_factory):
    """Test the attributes of the entity are correct."""
    # Arrange
    device = device_factory('Motion Sensor 1', [Capability.motion_sensor],
                            {Attribute.motion: 'inactive'})
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    device_registry = await hass.helpers.device_registry.async_get_registry()
    # Act
    await _setup_platform(hass, device)
    # Assert
    entry = entity_registry.async_get('binary_sensor.motion_sensor_1_motion')
    assert entry
    assert entry.unique_id == device.device_id + '.' + Attribute.motion
    entry = device_registry.async_get_device(
        {(DOMAIN, device.device_id)}, [])
    assert entry
    assert entry.name == device.label
    assert entry.model == device.device_type_name
    assert entry.manufacturer == 'Unavailable'


async def test_update_from_signal(hass, device_factory):
    """Test the binary_sensor updates when receiving a signal."""
    # Arrange
    device = device_factory('Motion Sensor 1', [Capability.motion_sensor],
                            {Attribute.motion: 'inactive'})
    await _setup_platform(hass, device)
    device.status.apply_attribute_update(
        'main', Capability.motion_sensor, Attribute.motion, 'active')
    # Act
    async_dispatcher_send(hass, SIGNAL_SMARTTHINGS_UPDATE,
                          [device.device_id])
    # Assert
    await hass.async_block_till_done()
    state = hass.states.get('binary_sensor.motion_sensor_1_motion')
    assert state is not None
    assert state.state == 'on'


async def test_unload_config_entry(hass, device_factory):
    """Test the binary_sensor is removed when the config entry is unloaded."""
    # Arrange
    device = device_factory('Motion Sensor 1', [Capability.motion_sensor],
                            {Attribute.motion: 'inactive'})
    config_entry = await _setup_platform(hass, device)
    # Act
    await hass.config_entries.async_forward_entry_unload(
        config_entry, 'binary_sensor')
    # Assert
    assert not hass.states.get('binary_sensor.motion_sensor_1_motion')
