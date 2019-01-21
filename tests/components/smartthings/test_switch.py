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


def test_is_switch(device_factory):
    """Test switches are correctly identified."""
    switch_device = device_factory('Switch', [Capability.switch])
    non_switch_devices = [
        device_factory('Light', [Capability.switch, Capability.switch_level]),
        device_factory('Fan', [Capability.switch, Capability.fan_speed]),
        device_factory('Color Light', [Capability.switch,
                                       Capability.color_control]),
        device_factory('Temp Light', [Capability.switch,
                                      Capability.color_temperature]),
        device_factory('Unknown', ['Unknown']),
    ]
    assert switch.is_switch(switch_device)
    for non_switch_device in non_switch_devices:
        assert not switch.is_switch(non_switch_device)


class TestSmartThingsSwitch:
    """Tests for the SmartThingsSwitch."""

    @staticmethod
    async def test_entity_attributes(hass, device_factory):
        """Test the attributes of the entity are correct."""
        # Arrange
        device = device_factory('Switch_1', [Capability.switch],
                                {Attribute.switch: 'on'})
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
                (DOMAIN, device.device_id)
            },
            'name': device.label,
            'model': device.device_type_name,
            'manufacturer': 'SmartThings'
        }

    @staticmethod
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
        entity = hass.states.get('switch.switch_1')
        assert entity is not None
        assert entity.state == 'off'

    @staticmethod
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
        entity = hass.states.get('switch.switch_1')
        assert entity is not None
        assert entity.state == 'on'

    @staticmethod
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
        entity = hass.states.get('switch.switch_1')
        assert entity is not None
        assert entity.state == 'on'

    @staticmethod
    async def test_unload_config_entry(hass, device_factory):
        """Test the switch is removed when the config entry is unloaded."""
        # Arrange
        device = device_factory('Switch', [Capability.switch],
                                {Attribute.switch: 'on'})
        config_entry = await _setup_platform(hass, device)
        # Act
        await hass.config_entries.async_forward_entry_unload(
            config_entry, 'switch')
        # Assert
        assert not hass.states.get('switch.switch_1')
