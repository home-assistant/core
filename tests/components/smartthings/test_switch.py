"""
Test for the SmartThings switch platform.

The only mocking required is of the underlying SmartThings API object so
real HTTP calls are not initiated during testing.
"""
from pysmartthings import Attribute, Capability

from homeassistant.components.smartthings import DeviceBroker, switch
from homeassistant.components.smartthings.const import (
    DATA_BROKERS, DOMAIN, SIGNAL_SMARTTHINGS_UPDATE)
from homeassistant.config_entries import (
    CONN_CLASS_CLOUD_PUSH, SOURCE_USER, ConfigEntry)
from homeassistant.helpers.dispatcher import async_dispatcher_send


async def _setup_platform(hass, *devices):
    """Set up the SmartThings switch platform and prerequisites."""
    hass.config.components.add(DOMAIN)
    broker = DeviceBroker(hass, devices, '')
    config_entry = ConfigEntry("1", DOMAIN, "Test", {},
                               SOURCE_USER, CONN_CLASS_CLOUD_PUSH)
    hass.data[DOMAIN] = {
        DATA_BROKERS: {
            config_entry.entry_id: broker
        }
    }
    await hass.config_entries.async_forward_entry_setup(config_entry, 'switch')
    await hass.async_block_till_done()
    return config_entry


async def test_async_setup_platform():
    """Test setup platform does nothing (it uses config entries)."""
    await switch.async_setup_platform(None, None, None)


async def test_entity_and_device_attributes(hass, device_factory):
    """Test the attributes of the entity are correct."""
    # Arrange
    device = device_factory('Switch_1', [Capability.switch],
                            {Attribute.switch: 'on'})
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    device_registry = await hass.helpers.device_registry.async_get_registry()
    # Act
    await _setup_platform(hass, device)
    # Assert
    entry = entity_registry.async_get('switch.switch_1')
    assert entry
    assert entry.unique_id == device.device_id

    entry = device_registry.async_get_device(
        {(DOMAIN, device.device_id)}, [])
    assert entry
    assert entry.name == device.label
    assert entry.model == device.device_type_name
    assert entry.manufacturer == 'Unavailable'


async def test_turn_off(hass, device_factory):
    """Test the switch turns of successfully."""
    # Arrange
    device = device_factory('Switch_1', [Capability.switch],
                            {Attribute.switch: 'on'})
    await _setup_platform(hass, device)
    # Act
    await hass.services.async_call(
        'switch', 'turn_off', {'entity_id': 'switch.switch_1'},
        blocking=True)
    # Assert
    state = hass.states.get('switch.switch_1')
    assert state is not None
    assert state.state == 'off'


async def test_turn_on(hass, device_factory):
    """Test the switch turns of successfully."""
    # Arrange
    device = device_factory('Switch_1', [Capability.switch],
                            {Attribute.switch: 'off'})
    await _setup_platform(hass, device)
    # Act
    await hass.services.async_call(
        'switch', 'turn_on', {'entity_id': 'switch.switch_1'},
        blocking=True)
    # Assert
    state = hass.states.get('switch.switch_1')
    assert state is not None
    assert state.state == 'on'


async def test_update_from_signal(hass, device_factory):
    """Test the switch updates when receiving a signal."""
    # Arrange
    device = device_factory('Switch_1', [Capability.switch],
                            {Attribute.switch: 'off'})
    await _setup_platform(hass, device)
    await device.switch_on(True)
    # Act
    async_dispatcher_send(hass, SIGNAL_SMARTTHINGS_UPDATE,
                          [device.device_id])
    # Assert
    await hass.async_block_till_done()
    state = hass.states.get('switch.switch_1')
    assert state is not None
    assert state.state == 'on'


async def test_unload_config_entry(hass, device_factory):
    """Test the switch is removed when the config entry is unloaded."""
    # Arrange
    device = device_factory('Switch 1', [Capability.switch],
                            {Attribute.switch: 'on'})
    config_entry = await _setup_platform(hass, device)
    # Act
    await hass.config_entries.async_forward_entry_unload(
        config_entry, 'switch')
    # Assert
    assert not hass.states.get('switch.switch_1')
