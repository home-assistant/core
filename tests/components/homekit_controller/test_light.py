"""Basic checks for HomeKitSwitch."""

from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.components.homekit_controller.const import KNOWN_DEVICES
from homeassistant.components.light import (
    ATTR_COLOR_MODE,
    ATTR_SUPPORTED_COLOR_MODES,
    ColorMode,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import get_next_aid, setup_test_component

LIGHT_BULB_NAME = "TestDevice"
LIGHT_BULB_ENTITY_ID = "light.testdevice"


def create_lightbulb_service(accessory):
    """Define lightbulb characteristics."""
    service = accessory.add_service(ServicesTypes.LIGHTBULB, name=LIGHT_BULB_NAME)

    on_char = service.add_char(CharacteristicsTypes.ON)
    on_char.value = 0

    brightness = service.add_char(CharacteristicsTypes.BRIGHTNESS)
    brightness.value = 0

    return service


def create_lightbulb_service_with_hs(accessory):
    """Define a lightbulb service with hue + saturation."""
    service = create_lightbulb_service(accessory)

    hue = service.add_char(CharacteristicsTypes.HUE)
    hue.value = 0

    saturation = service.add_char(CharacteristicsTypes.SATURATION)
    saturation.value = 0

    return service


def create_lightbulb_service_with_color_temp(accessory):
    """Define a lightbulb service with color temp."""
    service = create_lightbulb_service(accessory)

    color_temp = service.add_char(CharacteristicsTypes.COLOR_TEMPERATURE)
    color_temp.value = 0

    return service


async def test_switch_change_light_state(hass: HomeAssistant) -> None:
    """Test that we can turn a HomeKit light on and off again."""
    helper = await setup_test_component(hass, create_lightbulb_service_with_hs)

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.testdevice", "brightness": 255, "hs_color": [4, 5]},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.LIGHTBULB,
        {
            CharacteristicsTypes.ON: True,
            CharacteristicsTypes.BRIGHTNESS: 100,
            CharacteristicsTypes.HUE: 4,
            CharacteristicsTypes.SATURATION: 5,
        },
    )

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.testdevice", "brightness": 255, "color_temp": 300},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.LIGHTBULB,
        {
            CharacteristicsTypes.ON: True,
            CharacteristicsTypes.BRIGHTNESS: 100,
            CharacteristicsTypes.HUE: 27,
            CharacteristicsTypes.SATURATION: 49,
        },
    )

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.testdevice"}, blocking=True
    )
    helper.async_assert_service_values(
        ServicesTypes.LIGHTBULB,
        {
            CharacteristicsTypes.ON: False,
        },
    )


async def test_switch_change_light_state_color_temp(hass: HomeAssistant) -> None:
    """Test that we can turn change color_temp."""
    helper = await setup_test_component(hass, create_lightbulb_service_with_color_temp)

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.testdevice", "brightness": 255, "color_temp": 400},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.LIGHTBULB,
        {
            CharacteristicsTypes.ON: True,
            CharacteristicsTypes.BRIGHTNESS: 100,
            CharacteristicsTypes.COLOR_TEMPERATURE: 400,
        },
    )


async def test_switch_read_light_state_dimmer(hass: HomeAssistant) -> None:
    """Test that we can read the state of a HomeKit light accessory."""
    helper = await setup_test_component(hass, create_lightbulb_service)

    # Initial state is that the light is off
    state = await helper.poll_and_get_state()
    assert state.state == "off"
    assert state.attributes[ATTR_COLOR_MODE] is None
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    # Simulate that someone switched on the device in the real world not via HA
    state = await helper.async_update(
        ServicesTypes.LIGHTBULB,
        {
            CharacteristicsTypes.ON: True,
            CharacteristicsTypes.BRIGHTNESS: 100,
        },
    )
    assert state.state == "on"
    assert state.attributes["brightness"] == 255
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    # Simulate that device switched off in the real world not via HA
    state = await helper.async_update(
        ServicesTypes.LIGHTBULB,
        {
            CharacteristicsTypes.ON: False,
        },
    )
    assert state.state == "off"


async def test_switch_push_light_state_dimmer(hass: HomeAssistant) -> None:
    """Test that we can read the state of a HomeKit light accessory."""
    helper = await setup_test_component(hass, create_lightbulb_service)

    # Initial state is that the light is off
    state = hass.states.get(LIGHT_BULB_ENTITY_ID)
    assert state.state == "off"

    state = await helper.async_update(
        ServicesTypes.LIGHTBULB,
        {
            CharacteristicsTypes.ON: True,
            CharacteristicsTypes.BRIGHTNESS: 100,
        },
    )
    assert state.state == "on"
    assert state.attributes["brightness"] == 255

    # Simulate that device switched off in the real world not via HA
    state = await helper.async_update(
        ServicesTypes.LIGHTBULB,
        {
            CharacteristicsTypes.ON: False,
        },
    )
    assert state.state == "off"


async def test_switch_read_light_state_hs(hass: HomeAssistant) -> None:
    """Test that we can read the state of a HomeKit light accessory."""
    helper = await setup_test_component(hass, create_lightbulb_service_with_hs)

    # Initial state is that the light is off
    state = await helper.poll_and_get_state()
    assert state.state == "off"
    assert state.attributes[ATTR_COLOR_MODE] is None
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
    ]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    # Simulate that someone switched on the device in the real world not via HA
    state = await helper.async_update(
        ServicesTypes.LIGHTBULB,
        {
            CharacteristicsTypes.ON: True,
            CharacteristicsTypes.BRIGHTNESS: 100,
            CharacteristicsTypes.HUE: 4,
            CharacteristicsTypes.SATURATION: 5,
        },
    )
    assert state.state == "on"
    assert state.attributes["brightness"] == 255
    assert state.attributes["hs_color"] == (4, 5)
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.HS
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
    ]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    # Simulate that device switched off in the real world not via HA
    state = await helper.async_update(
        ServicesTypes.LIGHTBULB,
        {
            CharacteristicsTypes.ON: False,
        },
    )
    assert state.state == "off"

    # Simulate that device switched on in the real world not via HA
    state = await helper.async_update(
        ServicesTypes.LIGHTBULB,
        {
            CharacteristicsTypes.ON: True,
            CharacteristicsTypes.HUE: 6,
            CharacteristicsTypes.SATURATION: 7,
        },
    )
    assert state.state == "on"
    assert state.attributes["brightness"] == 255
    assert state.attributes["hs_color"] == (6, 7)
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.HS
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
    ]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0


async def test_switch_push_light_state_hs(hass: HomeAssistant) -> None:
    """Test that we can read the state of a HomeKit light accessory."""
    helper = await setup_test_component(hass, create_lightbulb_service_with_hs)

    # Initial state is that the light is off
    state = hass.states.get(LIGHT_BULB_ENTITY_ID)
    assert state.state == "off"

    state = await helper.async_update(
        ServicesTypes.LIGHTBULB,
        {
            CharacteristicsTypes.ON: True,
            CharacteristicsTypes.BRIGHTNESS: 100,
            CharacteristicsTypes.HUE: 4,
            CharacteristicsTypes.SATURATION: 5,
        },
    )
    assert state.state == "on"
    assert state.attributes["brightness"] == 255
    assert state.attributes["hs_color"] == (4, 5)

    # Simulate that device switched off in the real world not via HA
    state = await helper.async_update(
        ServicesTypes.LIGHTBULB,
        {
            CharacteristicsTypes.ON: False,
        },
    )
    assert state.state == "off"


async def test_switch_read_light_state_color_temp(hass: HomeAssistant) -> None:
    """Test that we can read the color_temp of a  light accessory."""
    helper = await setup_test_component(hass, create_lightbulb_service_with_color_temp)

    # Initial state is that the light is off
    state = await helper.poll_and_get_state()
    assert state.state == "off"
    assert state.attributes[ATTR_COLOR_MODE] is None
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.COLOR_TEMP]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    # Simulate that someone switched on the device in the real world not via HA
    state = await helper.async_update(
        ServicesTypes.LIGHTBULB,
        {
            CharacteristicsTypes.ON: True,
            CharacteristicsTypes.BRIGHTNESS: 100,
            CharacteristicsTypes.COLOR_TEMPERATURE: 400,
        },
    )
    assert state.state == "on"
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_temp"] == 400
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.COLOR_TEMP]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0


async def test_switch_push_light_state_color_temp(hass: HomeAssistant) -> None:
    """Test that we can read the state of a HomeKit light accessory."""
    helper = await setup_test_component(hass, create_lightbulb_service_with_color_temp)

    # Initial state is that the light is off
    state = hass.states.get(LIGHT_BULB_ENTITY_ID)
    assert state.state == "off"

    state = await helper.async_update(
        ServicesTypes.LIGHTBULB,
        {
            CharacteristicsTypes.ON: True,
            CharacteristicsTypes.BRIGHTNESS: 100,
            CharacteristicsTypes.COLOR_TEMPERATURE: 400,
        },
    )
    assert state.state == "on"
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_temp"] == 400


async def test_light_becomes_unavailable_but_recovers(hass: HomeAssistant) -> None:
    """Test transition to and from unavailable state."""
    helper = await setup_test_component(hass, create_lightbulb_service_with_color_temp)

    # Initial state is that the light is off
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    # Test device goes offline
    helper.pairing.available = False
    state = await helper.poll_and_get_state()
    assert state.state == "unavailable"

    # Simulate that someone switched on the device in the real world not via HA
    helper.pairing.available = True
    state = await helper.async_update(
        ServicesTypes.LIGHTBULB,
        {
            CharacteristicsTypes.ON: True,
            CharacteristicsTypes.BRIGHTNESS: 100,
            CharacteristicsTypes.COLOR_TEMPERATURE: 400,
        },
    )
    assert state.state == "on"
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_temp"] == 400


async def test_light_unloaded_removed(hass: HomeAssistant) -> None:
    """Test entity and HKDevice are correctly unloaded and removed."""
    helper = await setup_test_component(hass, create_lightbulb_service_with_color_temp)

    # Initial state is that the light is off
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    unload_result = await helper.config_entry.async_unload(hass)
    assert unload_result is True

    # Make sure entity is set to unavailable state
    assert hass.states.get(helper.entity_id).state == STATE_UNAVAILABLE

    # Make sure HKDevice is no longer set to poll this accessory
    conn = hass.data[KNOWN_DEVICES]["00:00:00:00:00:00"]
    assert not conn.pollable_characteristics

    await helper.config_entry.async_remove(hass)
    await hass.async_block_till_done()

    # Make sure entity is removed
    assert hass.states.get(helper.entity_id).state == STATE_UNAVAILABLE


async def test_migrate_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a we can migrate a light unique id."""
    aid = get_next_aid()
    light_entry = entity_registry.async_get_or_create(
        "light",
        "homekit_controller",
        f"homekit-00:00:00:00:00:00-{aid}-8",
    )
    await setup_test_component(hass, create_lightbulb_service_with_color_temp)

    assert (
        entity_registry.async_get(light_entry.entity_id).unique_id
        == f"00:00:00:00:00:00_{aid}_8"
    )


async def test_only_migrate_once(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a we handle migration happening after an upgrade and than a downgrade and then an upgrade."""
    aid = get_next_aid()
    old_light_entry = entity_registry.async_get_or_create(
        "light",
        "homekit_controller",
        f"homekit-00:00:00:00:00:00-{aid}-8",
    )
    new_light_entry = entity_registry.async_get_or_create(
        "light",
        "homekit_controller",
        f"00:00:00:00:00:00_{aid}_8",
    )
    await setup_test_component(hass, create_lightbulb_service_with_color_temp)

    assert (
        entity_registry.async_get(old_light_entry.entity_id).unique_id
        == f"homekit-00:00:00:00:00:00-{aid}-8"
    )

    assert (
        entity_registry.async_get(new_light_entry.entity_id).unique_id
        == f"00:00:00:00:00:00_{aid}_8"
    )
