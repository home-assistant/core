"""
Test for the SmartThings light platform.

The only mocking required is of the underlying SmartThings API object so
real HTTP calls are not initiated during testing.
"""
from pysmartthings import Attribute, Capability
import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_TRANSITION,
)
from homeassistant.components.smartthings.const import DOMAIN, SIGNAL_SMARTTHINGS_UPDATE
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .conftest import setup_platform


@pytest.fixture(name="light_devices")
def light_devices_fixture(device_factory):
    """Fixture returns a set of mock light devices."""
    return [
        device_factory(
            "Dimmer 1",
            capabilities=[Capability.switch, Capability.switch_level],
            status={Attribute.switch: "on", Attribute.level: 100},
        ),
        device_factory(
            "Color Dimmer 1",
            capabilities=[
                Capability.switch,
                Capability.switch_level,
                Capability.color_control,
            ],
            status={
                Attribute.switch: "off",
                Attribute.level: 0,
                Attribute.hue: 76.0,
                Attribute.saturation: 55.0,
            },
        ),
        device_factory(
            "Color Dimmer 2",
            capabilities=[
                Capability.switch,
                Capability.switch_level,
                Capability.color_control,
                Capability.color_temperature,
            ],
            status={
                Attribute.switch: "on",
                Attribute.level: 100,
                Attribute.hue: 76.0,
                Attribute.saturation: 55.0,
                Attribute.color_temperature: 4500,
            },
        ),
    ]


async def test_entity_state(hass, light_devices):
    """Tests the state attributes properly match the light types."""
    await setup_platform(hass, LIGHT_DOMAIN, devices=light_devices)

    # Dimmer 1
    state = hass.states.get("light.dimmer_1")
    assert state.state == "on"
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION
    )
    assert isinstance(state.attributes[ATTR_BRIGHTNESS], int)
    assert state.attributes[ATTR_BRIGHTNESS] == 255

    # Color Dimmer 1
    state = hass.states.get("light.color_dimmer_1")
    assert state.state == "off"
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION | SUPPORT_COLOR
    )

    # Color Dimmer 2
    state = hass.states.get("light.color_dimmer_2")
    assert state.state == "on"
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION | SUPPORT_COLOR | SUPPORT_COLOR_TEMP
    )
    assert state.attributes[ATTR_BRIGHTNESS] == 255
    assert state.attributes[ATTR_HS_COLOR] == (273.6, 55.0)
    assert isinstance(state.attributes[ATTR_COLOR_TEMP], int)
    assert state.attributes[ATTR_COLOR_TEMP] == 222


async def test_entity_and_device_attributes(hass, device_factory):
    """Test the attributes of the entity are correct."""
    # Arrange
    device = device_factory("Light 1", [Capability.switch, Capability.switch_level])
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    device_registry = await hass.helpers.device_registry.async_get_registry()
    # Act
    await setup_platform(hass, LIGHT_DOMAIN, devices=[device])
    # Assert
    entry = entity_registry.async_get("light.light_1")
    assert entry
    assert entry.unique_id == device.device_id

    entry = device_registry.async_get_device({(DOMAIN, device.device_id)}, [])
    assert entry
    assert entry.name == device.label
    assert entry.model == device.device_type_name
    assert entry.manufacturer == "Unavailable"


async def test_turn_off(hass, light_devices):
    """Test the light turns of successfully."""
    # Arrange
    await setup_platform(hass, LIGHT_DOMAIN, devices=light_devices)
    # Act
    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.color_dimmer_2"}, blocking=True
    )
    # Assert
    state = hass.states.get("light.color_dimmer_2")
    assert state is not None
    assert state.state == "off"


async def test_turn_off_with_transition(hass, light_devices):
    """Test the light turns of successfully with transition."""
    # Arrange
    await setup_platform(hass, LIGHT_DOMAIN, devices=light_devices)
    # Act
    await hass.services.async_call(
        "light",
        "turn_off",
        {ATTR_ENTITY_ID: "light.color_dimmer_2", ATTR_TRANSITION: 2},
        blocking=True,
    )
    # Assert
    state = hass.states.get("light.color_dimmer_2")
    assert state is not None
    assert state.state == "off"


async def test_turn_on(hass, light_devices):
    """Test the light turns of successfully."""
    # Arrange
    await setup_platform(hass, LIGHT_DOMAIN, devices=light_devices)
    # Act
    await hass.services.async_call(
        "light", "turn_on", {ATTR_ENTITY_ID: "light.color_dimmer_1"}, blocking=True
    )
    # Assert
    state = hass.states.get("light.color_dimmer_1")
    assert state is not None
    assert state.state == "on"


async def test_turn_on_with_brightness(hass, light_devices):
    """Test the light turns on to the specified brightness."""
    # Arrange
    await setup_platform(hass, LIGHT_DOMAIN, devices=light_devices)
    # Act
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            ATTR_ENTITY_ID: "light.color_dimmer_1",
            ATTR_BRIGHTNESS: 75,
            ATTR_TRANSITION: 2,
        },
        blocking=True,
    )
    # Assert
    state = hass.states.get("light.color_dimmer_1")
    assert state is not None
    assert state.state == "on"
    # round-trip rounding error (expected)
    assert state.attributes[ATTR_BRIGHTNESS] == 74


async def test_turn_on_with_minimal_brightness(hass, light_devices):
    """
    Test lights set to lowest brightness when converted scale would be zero.

    SmartThings light brightness is a percentage (0-100), but Home Assistant uses a
    0-255 scale.  This tests if a really low value (1-2) is passed, we don't
    set the level to zero, which turns off the lights in SmartThings.
    """
    # Arrange
    await setup_platform(hass, LIGHT_DOMAIN, devices=light_devices)
    # Act
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.color_dimmer_1", ATTR_BRIGHTNESS: 2},
        blocking=True,
    )
    # Assert
    state = hass.states.get("light.color_dimmer_1")
    assert state is not None
    assert state.state == "on"
    # round-trip rounding error (expected)
    assert state.attributes[ATTR_BRIGHTNESS] == 3


async def test_turn_on_with_color(hass, light_devices):
    """Test the light turns on with color."""
    # Arrange
    await setup_platform(hass, LIGHT_DOMAIN, devices=light_devices)
    # Act
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.color_dimmer_2", ATTR_HS_COLOR: (180, 50)},
        blocking=True,
    )
    # Assert
    state = hass.states.get("light.color_dimmer_2")
    assert state is not None
    assert state.state == "on"
    assert state.attributes[ATTR_HS_COLOR] == (180, 50)


async def test_turn_on_with_color_temp(hass, light_devices):
    """Test the light turns on with color temp."""
    # Arrange
    await setup_platform(hass, LIGHT_DOMAIN, devices=light_devices)
    # Act
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.color_dimmer_2", ATTR_COLOR_TEMP: 300},
        blocking=True,
    )
    # Assert
    state = hass.states.get("light.color_dimmer_2")
    assert state is not None
    assert state.state == "on"
    assert state.attributes[ATTR_COLOR_TEMP] == 300


async def test_update_from_signal(hass, device_factory):
    """Test the light updates when receiving a signal."""
    # Arrange
    device = device_factory(
        "Color Dimmer 2",
        capabilities=[
            Capability.switch,
            Capability.switch_level,
            Capability.color_control,
            Capability.color_temperature,
        ],
        status={
            Attribute.switch: "off",
            Attribute.level: 100,
            Attribute.hue: 76.0,
            Attribute.saturation: 55.0,
            Attribute.color_temperature: 4500,
        },
    )
    await setup_platform(hass, LIGHT_DOMAIN, devices=[device])
    await device.switch_on(True)
    # Act
    async_dispatcher_send(hass, SIGNAL_SMARTTHINGS_UPDATE, [device.device_id])
    # Assert
    await hass.async_block_till_done()
    state = hass.states.get("light.color_dimmer_2")
    assert state is not None
    assert state.state == "on"


async def test_unload_config_entry(hass, device_factory):
    """Test the light is removed when the config entry is unloaded."""
    # Arrange
    device = device_factory(
        "Color Dimmer 2",
        capabilities=[
            Capability.switch,
            Capability.switch_level,
            Capability.color_control,
            Capability.color_temperature,
        ],
        status={
            Attribute.switch: "off",
            Attribute.level: 100,
            Attribute.hue: 76.0,
            Attribute.saturation: 55.0,
            Attribute.color_temperature: 4500,
        },
    )
    config_entry = await setup_platform(hass, LIGHT_DOMAIN, devices=[device])
    # Act
    await hass.config_entries.async_forward_entry_unload(config_entry, "light")
    # Assert
    assert not hass.states.get("light.color_dimmer_2")
