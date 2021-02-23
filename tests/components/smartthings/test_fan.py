"""
Test for the SmartThings fan platform.

The only mocking required is of the underlying SmartThings API object so
real HTTP calls are not initiated during testing.
"""
from pysmartthings import Attribute, Capability

from homeassistant.components.fan import (
    ATTR_SPEED,
    ATTR_SPEED_LIST,
    DOMAIN as FAN_DOMAIN,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
)
from homeassistant.components.smartthings.const import DOMAIN, SIGNAL_SMARTTHINGS_UPDATE
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .conftest import setup_platform


async def test_entity_state(hass, device_factory):
    """Tests the state attributes properly match the fan types."""
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={Attribute.switch: "on", Attribute.fan_speed: 2},
    )
    await setup_platform(hass, FAN_DOMAIN, devices=[device])

    # Dimmer 1
    state = hass.states.get("fan.fan_1")
    assert state.state == "on"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_SET_SPEED
    assert state.attributes[ATTR_SPEED] == SPEED_MEDIUM
    assert state.attributes[ATTR_SPEED_LIST] == [
        SPEED_OFF,
        SPEED_LOW,
        SPEED_MEDIUM,
        SPEED_HIGH,
    ]


async def test_entity_and_device_attributes(hass, device_factory):
    """Test the attributes of the entity are correct."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={Attribute.switch: "on", Attribute.fan_speed: 2},
    )
    # Act
    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    device_registry = await hass.helpers.device_registry.async_get_registry()
    # Assert
    entry = entity_registry.async_get("fan.fan_1")
    assert entry
    assert entry.unique_id == device.device_id

    entry = device_registry.async_get_device({(DOMAIN, device.device_id)})
    assert entry
    assert entry.name == device.label
    assert entry.model == device.device_type_name
    assert entry.manufacturer == "Unavailable"


async def test_turn_off(hass, device_factory):
    """Test the fan turns of successfully."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={Attribute.switch: "on", Attribute.fan_speed: 2},
    )
    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        "fan", "turn_off", {"entity_id": "fan.fan_1"}, blocking=True
    )
    # Assert
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.state == "off"


async def test_turn_on(hass, device_factory):
    """Test the fan turns of successfully."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={Attribute.switch: "off", Attribute.fan_speed: 0},
    )
    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        "fan", "turn_on", {ATTR_ENTITY_ID: "fan.fan_1"}, blocking=True
    )
    # Assert
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.state == "on"


async def test_turn_on_with_speed(hass, device_factory):
    """Test the fan turns on to the specified speed."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={Attribute.switch: "off", Attribute.fan_speed: 0},
    )
    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        "fan",
        "turn_on",
        {ATTR_ENTITY_ID: "fan.fan_1", ATTR_SPEED: SPEED_HIGH},
        blocking=True,
    )
    # Assert
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.state == "on"
    assert state.attributes[ATTR_SPEED] == SPEED_HIGH


async def test_set_speed(hass, device_factory):
    """Test setting to specific fan speed."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={Attribute.switch: "off", Attribute.fan_speed: 0},
    )
    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        "fan",
        "set_speed",
        {ATTR_ENTITY_ID: "fan.fan_1", ATTR_SPEED: SPEED_HIGH},
        blocking=True,
    )
    # Assert
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.state == "on"
    assert state.attributes[ATTR_SPEED] == SPEED_HIGH


async def test_update_from_signal(hass, device_factory):
    """Test the fan updates when receiving a signal."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={Attribute.switch: "off", Attribute.fan_speed: 0},
    )
    await setup_platform(hass, FAN_DOMAIN, devices=[device])
    await device.switch_on(True)
    # Act
    async_dispatcher_send(hass, SIGNAL_SMARTTHINGS_UPDATE, [device.device_id])
    # Assert
    await hass.async_block_till_done()
    state = hass.states.get("fan.fan_1")
    assert state is not None
    assert state.state == "on"


async def test_unload_config_entry(hass, device_factory):
    """Test the fan is removed when the config entry is unloaded."""
    # Arrange
    device = device_factory(
        "Fan 1",
        capabilities=[Capability.switch, Capability.fan_speed],
        status={Attribute.switch: "off", Attribute.fan_speed: 0},
    )
    config_entry = await setup_platform(hass, FAN_DOMAIN, devices=[device])
    # Act
    await hass.config_entries.async_forward_entry_unload(config_entry, "fan")
    # Assert
    assert hass.states.get("fan.fan_1").state == STATE_UNAVAILABLE
