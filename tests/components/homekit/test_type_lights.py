"""Test different accessory types: Lights."""
from collections import namedtuple

from pyhap.const import HAP_REPR_AID, HAP_REPR_CHARS, HAP_REPR_IID, HAP_REPR_VALUE
import pytest

from homeassistant.components.homekit.const import ATTR_VALUE
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    DOMAIN,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    EVENT_HOMEASSISTANT_START,
    PERCENTAGE,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState
from homeassistant.helpers import entity_registry

from tests.common import async_mock_service
from tests.components.homekit.common import patch_debounce


@pytest.fixture(scope="module")
def cls():
    """Patch debounce decorator during import of type_lights."""
    patcher = patch_debounce()
    patcher.start()
    _import = __import__(
        "homeassistant.components.homekit.type_lights", fromlist=["Light"]
    )
    patcher_tuple = namedtuple("Cls", ["light"])
    yield patcher_tuple(light=_import.Light)
    patcher.stop()


async def test_light_basic(hass, hk_driver, cls, events):
    """Test light with char state."""
    entity_id = "light.demo"

    hass.states.async_set(entity_id, STATE_ON, {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    acc = cls.light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.aid == 1
    assert acc.category == 5  # Lightbulb
    assert acc.char_on.value

    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc.char_on.value == 1

    hass.states.async_set(entity_id, STATE_OFF, {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    assert acc.char_on.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_on.value == 0

    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()
    assert acc.char_on.value == 0

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, "turn_on")
    call_turn_off = async_mock_service(hass, DOMAIN, "turn_off")

    char_on_iid = acc.char_on.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {HAP_REPR_AID: acc.aid, HAP_REPR_IID: char_on_iid, HAP_REPR_VALUE: 1}
            ]
        },
        "mock_addr",
    )

    await hass.async_add_executor_job(acc.char_on.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "Set state to 1"

    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {HAP_REPR_AID: acc.aid, HAP_REPR_IID: char_on_iid, HAP_REPR_VALUE: 0}
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == "Set state to 0"


async def test_light_brightness(hass, hk_driver, cls, events):
    """Test light with brightness."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_FEATURES: SUPPORT_BRIGHTNESS, ATTR_BRIGHTNESS: 255},
    )
    await hass.async_block_till_done()
    acc = cls.light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    # Initial value can be anything but 0. If it is 0, it might cause HomeKit to set the
    # brightness to 100 when turning on a light on a freshly booted up server.
    assert acc.char_brightness.value != 0
    char_on_iid = acc.char_on.to_HAP()[HAP_REPR_IID]
    char_brightness_iid = acc.char_brightness.to_HAP()[HAP_REPR_IID]

    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 100

    hass.states.async_set(entity_id, STATE_ON, {ATTR_BRIGHTNESS: 102})
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 40

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, "turn_on")
    call_turn_off = async_mock_service(hass, DOMAIN, "turn_off")

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {HAP_REPR_AID: acc.aid, HAP_REPR_IID: char_on_iid, HAP_REPR_VALUE: 1},
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_brightness_iid,
                    HAP_REPR_VALUE: 20,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_turn_on[0]
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[0].data[ATTR_BRIGHTNESS_PCT] == 20
    assert len(events) == 1
    assert (
        events[-1].data[ATTR_VALUE] == f"Set state to 1, brightness at 20{PERCENTAGE}"
    )

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {HAP_REPR_AID: acc.aid, HAP_REPR_IID: char_on_iid, HAP_REPR_VALUE: 1},
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_brightness_iid,
                    HAP_REPR_VALUE: 40,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_turn_on[1]
    assert call_turn_on[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[1].data[ATTR_BRIGHTNESS_PCT] == 40
    assert len(events) == 2
    assert (
        events[-1].data[ATTR_VALUE] == f"Set state to 1, brightness at 40{PERCENTAGE}"
    )

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {HAP_REPR_AID: acc.aid, HAP_REPR_IID: char_on_iid, HAP_REPR_VALUE: 1},
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_brightness_iid,
                    HAP_REPR_VALUE: 0,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 3
    assert events[-1].data[ATTR_VALUE] == f"Set state to 0, brightness at 0{PERCENTAGE}"

    # 0 is a special case for homekit, see "Handle Brightness"
    # in update_state
    hass.states.async_set(entity_id, STATE_ON, {ATTR_BRIGHTNESS: 0})
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 1
    hass.states.async_set(entity_id, STATE_ON, {ATTR_BRIGHTNESS: 255})
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 100
    hass.states.async_set(entity_id, STATE_ON, {ATTR_BRIGHTNESS: 0})
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 1

    # Ensure floats are handled
    hass.states.async_set(entity_id, STATE_ON, {ATTR_BRIGHTNESS: 55.66})
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 22
    hass.states.async_set(entity_id, STATE_ON, {ATTR_BRIGHTNESS: 108.4})
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 43
    hass.states.async_set(entity_id, STATE_ON, {ATTR_BRIGHTNESS: 0.0})
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 1


async def test_light_color_temperature(hass, hk_driver, cls, events):
    """Test light with color temperature."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_FEATURES: SUPPORT_COLOR_TEMP, ATTR_COLOR_TEMP: 190},
    )
    await hass.async_block_till_done()
    acc = cls.light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_color_temperature.value == 190

    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc.char_color_temperature.value == 190

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, "turn_on")

    char_color_temperature_iid = acc.char_color_temperature.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_color_temperature_iid,
                    HAP_REPR_VALUE: 250,
                }
            ]
        },
        "mock_addr",
    )
    await hass.async_add_executor_job(
        acc.char_color_temperature.client_update_value, 250
    )
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[0].data[ATTR_COLOR_TEMP] == 250
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "color temperature at 250"


async def test_light_color_temperature_and_rgb_color(hass, hk_driver, cls, events):
    """Test light with color temperature and rgb color not exposing temperature."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_COLOR_TEMP | SUPPORT_COLOR,
            ATTR_COLOR_TEMP: 190,
            ATTR_HS_COLOR: (260, 90),
        },
    )
    await hass.async_block_till_done()
    acc = cls.light(hass, hk_driver, "Light", entity_id, 2, None)
    assert acc.char_hue.value == 260
    assert acc.char_saturation.value == 90

    assert not hasattr(acc, "char_color_temperature")

    hass.states.async_set(entity_id, STATE_ON, {ATTR_COLOR_TEMP: 224})
    await hass.async_block_till_done()
    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc.char_hue.value == 27
    assert acc.char_saturation.value == 27

    hass.states.async_set(entity_id, STATE_ON, {ATTR_COLOR_TEMP: 352})
    await hass.async_block_till_done()
    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc.char_hue.value == 28
    assert acc.char_saturation.value == 61


async def test_light_rgb_color(hass, hk_driver, cls, events):
    """Test light with rgb_color."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_FEATURES: SUPPORT_COLOR, ATTR_HS_COLOR: (260, 90)},
    )
    await hass.async_block_till_done()
    acc = cls.light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_hue.value == 260
    assert acc.char_saturation.value == 90

    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc.char_hue.value == 260
    assert acc.char_saturation.value == 90

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, "turn_on")

    char_hue_iid = acc.char_hue.to_HAP()[HAP_REPR_IID]
    char_saturation_iid = acc.char_saturation.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_hue_iid,
                    HAP_REPR_VALUE: 145,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_saturation_iid,
                    HAP_REPR_VALUE: 75,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[0].data[ATTR_HS_COLOR] == (145, 75)
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "set color at (145, 75)"


async def test_light_restore(hass, hk_driver, cls, events):
    """Test setting up an entity from state in the event registry."""
    hass.state = CoreState.not_running

    registry = await entity_registry.async_get_registry(hass)

    registry.async_get_or_create("light", "hue", "1234", suggested_object_id="simple")
    registry.async_get_or_create(
        "light",
        "hue",
        "9012",
        suggested_object_id="all_info_set",
        capabilities={"max": 100},
        supported_features=5,
        device_class="mock-device-class",
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START, {})
    await hass.async_block_till_done()

    acc = cls.light(hass, hk_driver, "Light", "light.simple", 1, None)
    hk_driver.add_accessory(acc)

    assert acc.category == 5  # Lightbulb
    assert acc.chars == []
    assert acc.char_on.value == 0

    acc = cls.light(hass, hk_driver, "Light", "light.all_info_set", 2, None)
    assert acc.category == 5  # Lightbulb
    assert acc.chars == ["Brightness"]
    assert acc.char_on.value == 0


async def test_light_set_brightness_and_color(hass, hk_driver, cls, events):
    """Test light with all chars in one go."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_BRIGHTNESS | SUPPORT_COLOR,
            ATTR_BRIGHTNESS: 255,
        },
    )
    await hass.async_block_till_done()
    acc = cls.light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    # Initial value can be anything but 0. If it is 0, it might cause HomeKit to set the
    # brightness to 100 when turning on a light on a freshly booted up server.
    assert acc.char_brightness.value != 0
    char_on_iid = acc.char_on.to_HAP()[HAP_REPR_IID]
    char_brightness_iid = acc.char_brightness.to_HAP()[HAP_REPR_IID]
    char_hue_iid = acc.char_hue.to_HAP()[HAP_REPR_IID]
    char_saturation_iid = acc.char_saturation.to_HAP()[HAP_REPR_IID]

    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 100

    hass.states.async_set(entity_id, STATE_ON, {ATTR_BRIGHTNESS: 102})
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 40

    hass.states.async_set(entity_id, STATE_ON, {ATTR_HS_COLOR: (4.5, 9.2)})
    await hass.async_block_till_done()
    assert acc.char_hue.value == 4
    assert acc.char_saturation.value == 9

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, "turn_on")

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {HAP_REPR_AID: acc.aid, HAP_REPR_IID: char_on_iid, HAP_REPR_VALUE: 1},
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_brightness_iid,
                    HAP_REPR_VALUE: 20,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_hue_iid,
                    HAP_REPR_VALUE: 145,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_saturation_iid,
                    HAP_REPR_VALUE: 75,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_turn_on[0]
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[0].data[ATTR_BRIGHTNESS_PCT] == 20
    assert call_turn_on[0].data[ATTR_HS_COLOR] == (145, 75)

    assert len(events) == 1
    assert (
        events[-1].data[ATTR_VALUE]
        == f"Set state to 1, brightness at 20{PERCENTAGE}, set color at (145, 75)"
    )


async def test_light_set_brightness_and_color_temp(hass, hk_driver, cls, events):
    """Test light with all chars in one go."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP,
            ATTR_BRIGHTNESS: 255,
        },
    )
    await hass.async_block_till_done()
    acc = cls.light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    # Initial value can be anything but 0. If it is 0, it might cause HomeKit to set the
    # brightness to 100 when turning on a light on a freshly booted up server.
    assert acc.char_brightness.value != 0
    char_on_iid = acc.char_on.to_HAP()[HAP_REPR_IID]
    char_brightness_iid = acc.char_brightness.to_HAP()[HAP_REPR_IID]
    char_color_temperature_iid = acc.char_color_temperature.to_HAP()[HAP_REPR_IID]

    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 100

    hass.states.async_set(entity_id, STATE_ON, {ATTR_BRIGHTNESS: 102})
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 40

    hass.states.async_set(entity_id, STATE_ON, {ATTR_COLOR_TEMP: (224.14)})
    await hass.async_block_till_done()
    assert acc.char_color_temperature.value == 224

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, "turn_on")

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {HAP_REPR_AID: acc.aid, HAP_REPR_IID: char_on_iid, HAP_REPR_VALUE: 1},
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_brightness_iid,
                    HAP_REPR_VALUE: 20,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_color_temperature_iid,
                    HAP_REPR_VALUE: 250,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_turn_on[0]
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[0].data[ATTR_BRIGHTNESS_PCT] == 20
    assert call_turn_on[0].data[ATTR_COLOR_TEMP] == 250

    assert len(events) == 1
    assert (
        events[-1].data[ATTR_VALUE]
        == f"Set state to 1, brightness at 20{PERCENTAGE}, color temperature at 250"
    )
