"""Test different accessory types: Lights."""

from datetime import timedelta

from pyhap.const import HAP_REPR_AID, HAP_REPR_CHARS, HAP_REPR_IID, HAP_REPR_VALUE
import pytest

from homeassistant.components.homekit.const import (
    ATTR_VALUE,
    PROP_MAX_VALUE,
    PROP_MIN_VALUE,
)
from homeassistant.components.homekit.type_lights import (
    CHANGE_COALESCE_TIME_WINDOW,
    Light,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_WHITE,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
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
from homeassistant.core import CoreState, Event, HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, async_mock_service


async def _wait_for_light_coalesce(hass: HomeAssistant) -> None:
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=CHANGE_COALESCE_TIME_WINDOW)
    )
    await hass.async_block_till_done()


async def test_light_basic(hass: HomeAssistant, hk_driver, events: list[Event]) -> None:
    """Test light with char state."""
    entity_id = "light.demo"

    hass.states.async_set(entity_id, STATE_ON, {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.aid == 1
    assert acc.category == 5  # Lightbulb
    assert acc.char_on.value

    acc.run()
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
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    call_turn_off = async_mock_service(hass, LIGHT_DOMAIN, "turn_off")

    char_on_iid = acc.char_on.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {HAP_REPR_AID: acc.aid, HAP_REPR_IID: char_on_iid, HAP_REPR_VALUE: 1}
            ]
        },
        "mock_addr",
    )

    acc.char_on.client_update_value(1)
    await _wait_for_light_coalesce(hass)
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
    await _wait_for_light_coalesce(hass)
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == "Set state to 0"


@pytest.mark.parametrize(
    "supported_color_modes",
    [[ColorMode.BRIGHTNESS], [ColorMode.HS], [ColorMode.COLOR_TEMP]],
)
async def test_light_brightness(
    hass: HomeAssistant, hk_driver, events: list[Event], supported_color_modes
) -> None:
    """Test light with brightness."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_COLOR_MODES: supported_color_modes, ATTR_BRIGHTNESS: 255},
    )
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    # Initial value can be anything but 0. If it is 0, it might cause HomeKit to set the
    # brightness to 100 when turning on a light on a freshly booted up server.
    assert acc.char_brightness.value != 0
    char_on_iid = acc.char_on.to_HAP()[HAP_REPR_IID]
    char_brightness_iid = acc.char_brightness.to_HAP()[HAP_REPR_IID]

    acc.run()
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 100

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_COLOR_MODES: supported_color_modes, ATTR_BRIGHTNESS: 102},
    )
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 40

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    call_turn_off = async_mock_service(hass, LIGHT_DOMAIN, "turn_off")

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
    await _wait_for_light_coalesce(hass)
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
    await _wait_for_light_coalesce(hass)
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
    await _wait_for_light_coalesce(hass)
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 3
    assert events[-1].data[ATTR_VALUE] == f"Set state to 0, brightness at 0{PERCENTAGE}"

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_brightness_iid,
                    HAP_REPR_VALUE: 0,
                },
            ]
        },
        "mock_addr",
    )
    await _wait_for_light_coalesce(hass)
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 4
    assert events[-1].data[ATTR_VALUE] == f"Set state to 0, brightness at 0{PERCENTAGE}"

    # 0 is a special case for homekit, see "Handle Brightness"
    # in update_state
    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_COLOR_MODES: supported_color_modes, ATTR_BRIGHTNESS: 0},
    )
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 1
    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_COLOR_MODES: supported_color_modes, ATTR_BRIGHTNESS: 255},
    )
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 100
    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_COLOR_MODES: supported_color_modes, ATTR_BRIGHTNESS: 0},
    )
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 1

    # Ensure floats are handled
    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_COLOR_MODES: supported_color_modes, ATTR_BRIGHTNESS: 55.66},
    )
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 22
    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_COLOR_MODES: supported_color_modes, ATTR_BRIGHTNESS: 108.4},
    )
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 43
    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_COLOR_MODES: supported_color_modes, ATTR_BRIGHTNESS: 0.0},
    )
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 1


async def test_light_color_temperature(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test light with color temperature."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_COLOR_MODES: ["color_temp"], ATTR_COLOR_TEMP_KELVIN: 5263},
    )
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_color_temp.value == 190

    acc.run()
    await hass.async_block_till_done()
    assert acc.char_color_temp.value == 190

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    char_color_temp_iid = acc.char_color_temp.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_color_temp_iid,
                    HAP_REPR_VALUE: 250,
                }
            ]
        },
        "mock_addr",
    )
    await _wait_for_light_coalesce(hass)
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[0].data[ATTR_COLOR_TEMP_KELVIN] == 4000
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "color temperature at 250"


@pytest.mark.parametrize(
    "supported_color_modes",
    [["color_temp", "hs"], ["color_temp", "rgb"], ["color_temp", "xy"]],
)
async def test_light_color_temperature_and_rgb_color(
    hass: HomeAssistant, hk_driver, events: list[Event], supported_color_modes
) -> None:
    """Test light with color temperature and rgb color not exposing temperature."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_COLOR_MODES: supported_color_modes,
            ATTR_COLOR_TEMP_KELVIN: 5263,
            ATTR_HS_COLOR: (260, 90),
        },
    )
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_color_temp.value == 190
    assert acc.char_hue.value == 27
    assert acc.char_saturation.value == 16

    assert hasattr(acc, "char_color_temp")

    hass.states.async_set(entity_id, STATE_ON, {ATTR_COLOR_TEMP_KELVIN: 4464})
    await hass.async_block_till_done()
    acc.run()
    await hass.async_block_till_done()
    assert acc.char_color_temp.value == 224
    assert acc.char_hue.value == 27
    assert acc.char_saturation.value == 27

    hass.states.async_set(entity_id, STATE_ON, {ATTR_COLOR_TEMP_KELVIN: 2840})
    await hass.async_block_till_done()
    acc.run()
    await hass.async_block_till_done()
    assert acc.char_color_temp.value == 352
    assert acc.char_hue.value == 28
    assert acc.char_saturation.value == 61

    char_on_iid = acc.char_on.to_HAP()[HAP_REPR_IID]
    char_brightness_iid = acc.char_brightness.to_HAP()[HAP_REPR_IID]
    char_hue_iid = acc.char_hue.to_HAP()[HAP_REPR_IID]
    char_saturation_iid = acc.char_saturation.to_HAP()[HAP_REPR_IID]
    char_color_temp_iid = acc.char_color_temp.to_HAP()[HAP_REPR_IID]

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

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
                    HAP_REPR_IID: char_color_temp_iid,
                    HAP_REPR_VALUE: 250,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_hue_iid,
                    HAP_REPR_VALUE: 50,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_saturation_iid,
                    HAP_REPR_VALUE: 50,
                },
            ]
        },
        "mock_addr",
    )
    await _wait_for_light_coalesce(hass)
    assert call_turn_on[0]
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[0].data[ATTR_BRIGHTNESS_PCT] == 20
    assert call_turn_on[0].data[ATTR_COLOR_TEMP_KELVIN] == 4000

    assert len(events) == 1
    assert (
        events[-1].data[ATTR_VALUE]
        == f"Set state to 1, brightness at 20{PERCENTAGE}, color temperature at 250"
    )

    # Only set Hue
    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_hue_iid,
                    HAP_REPR_VALUE: 30,
                }
            ]
        },
        "mock_addr",
    )
    await _wait_for_light_coalesce(hass)
    assert call_turn_on[1]
    assert call_turn_on[1].data[ATTR_HS_COLOR] == (30, 50)

    assert events[-1].data[ATTR_VALUE] == "set color at (30, 50)"

    # Only set Saturation
    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_saturation_iid,
                    HAP_REPR_VALUE: 20,
                }
            ]
        },
        "mock_addr",
    )
    await _wait_for_light_coalesce(hass)
    assert call_turn_on[2]
    assert call_turn_on[2].data[ATTR_HS_COLOR] == (30, 20)

    assert events[-1].data[ATTR_VALUE] == "set color at (30, 20)"

    # Generate a conflict by setting hue and then color temp
    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_hue_iid,
                    HAP_REPR_VALUE: 80,
                }
            ]
        },
        "mock_addr",
    )
    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_color_temp_iid,
                    HAP_REPR_VALUE: 320,
                }
            ]
        },
        "mock_addr",
    )
    await _wait_for_light_coalesce(hass)
    assert call_turn_on[3]
    assert call_turn_on[3].data[ATTR_COLOR_TEMP_KELVIN] == 3125
    assert events[-1].data[ATTR_VALUE] == "color temperature at 320"

    # Generate a conflict by setting color temp then saturation
    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_color_temp_iid,
                    HAP_REPR_VALUE: 404,
                }
            ]
        },
        "mock_addr",
    )
    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_saturation_iid,
                    HAP_REPR_VALUE: 35,
                }
            ]
        },
        "mock_addr",
    )
    await _wait_for_light_coalesce(hass)
    assert call_turn_on[4]
    assert call_turn_on[4].data[ATTR_HS_COLOR] == (80, 35)
    assert events[-1].data[ATTR_VALUE] == "set color at (80, 35)"

    # Set from HASS
    hass.states.async_set(entity_id, STATE_ON, {ATTR_HS_COLOR: (100, 100)})
    await hass.async_block_till_done()
    acc.run()
    await hass.async_block_till_done()
    assert acc.char_color_temp.value == 404
    assert acc.char_hue.value == 100
    assert acc.char_saturation.value == 100


@pytest.mark.parametrize(
    "supported_color_modes", [[ColorMode.HS], [ColorMode.RGB], [ColorMode.XY]]
)
async def test_light_rgb_color(
    hass: HomeAssistant, hk_driver, events: list[Event], supported_color_modes
) -> None:
    """Test light with rgb_color."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_COLOR_MODES: supported_color_modes, ATTR_HS_COLOR: (260, 90)},
    )
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_hue.value == 260
    assert acc.char_saturation.value == 90

    acc.run()
    await hass.async_block_till_done()
    assert acc.char_hue.value == 260
    assert acc.char_saturation.value == 90

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

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
    await _wait_for_light_coalesce(hass)
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[0].data[ATTR_HS_COLOR] == (145, 75)
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "set color at (145, 75)"


async def test_light_restore(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, hk_driver
) -> None:
    """Test setting up an entity from state in the event registry."""
    hass.set_state(CoreState.not_running)

    entity_registry.async_get_or_create(
        "light", "hue", "1234", suggested_object_id="simple"
    )
    entity_registry.async_get_or_create(
        "light",
        "hue",
        "9012",
        suggested_object_id="all_info_set",
        capabilities={"supported_color_modes": ["brightness"], "max": 100},
        supported_features=5,
        original_device_class="mock-device-class",
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START, {})
    await hass.async_block_till_done()

    acc = Light(hass, hk_driver, "Light", "light.simple", 1, None)
    hk_driver.add_accessory(acc)

    assert acc.category == 5  # Lightbulb
    assert acc.chars == []
    assert acc.char_on.value == 0

    acc = Light(hass, hk_driver, "Light", "light.all_info_set", 2, None)
    assert acc.category == 5  # Lightbulb
    assert acc.chars == ["Brightness"]
    assert acc.char_on.value == 0


@pytest.mark.parametrize(
    ("supported_color_modes", "state_props", "turn_on_props_with_brightness"),
    [
        (
            [ColorMode.COLOR_TEMP, ColorMode.RGBW],
            {
                ATTR_RGBW_COLOR: (128, 50, 0, 255),
                ATTR_RGB_COLOR: (128, 50, 0),
                ATTR_HS_COLOR: (23.438, 100.0),
                ATTR_BRIGHTNESS: 255,
                ATTR_COLOR_MODE: ColorMode.RGBW,
            },
            {ATTR_HS_COLOR: (145, 75), ATTR_BRIGHTNESS_PCT: 25},
        ),
        (
            [ColorMode.COLOR_TEMP, ColorMode.RGBWW],
            {
                ATTR_RGBWW_COLOR: (128, 50, 0, 255, 255),
                ATTR_RGB_COLOR: (128, 50, 0),
                ATTR_HS_COLOR: (23.438, 100.0),
                ATTR_BRIGHTNESS: 255,
                ATTR_COLOR_MODE: ColorMode.RGBWW,
            },
            {ATTR_HS_COLOR: (145, 75), ATTR_BRIGHTNESS_PCT: 25},
        ),
    ],
)
async def test_light_rgb_with_color_temp(
    hass: HomeAssistant,
    hk_driver,
    events: list[Event],
    supported_color_modes,
    state_props,
    turn_on_props_with_brightness,
) -> None:
    """Test lights with RGBW/RGBWW with color temp support."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_COLOR_MODES: supported_color_modes, **state_props},
    )
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_hue.value == 23
    assert acc.char_saturation.value == 100

    acc.run()
    await hass.async_block_till_done()
    assert acc.char_hue.value == 23
    assert acc.char_saturation.value == 100
    assert acc.char_brightness.value == 100

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    char_hue_iid = acc.char_hue.to_HAP()[HAP_REPR_IID]
    char_saturation_iid = acc.char_saturation.to_HAP()[HAP_REPR_IID]
    char_brightness_iid = acc.char_brightness.to_HAP()[HAP_REPR_IID]

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
    await _wait_for_light_coalesce(hass)
    assert call_turn_on
    assert call_turn_on[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[-1].data[ATTR_HS_COLOR] == (145, 75)
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "set color at (145, 75)"
    assert acc.char_brightness.value == 100

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
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_brightness_iid,
                    HAP_REPR_VALUE: 25,
                },
            ]
        },
        "mock_addr",
    )
    await _wait_for_light_coalesce(hass)
    assert call_turn_on
    assert call_turn_on[-1].data[ATTR_ENTITY_ID] == entity_id
    for k, v in turn_on_props_with_brightness.items():
        assert call_turn_on[-1].data[k] == v
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == "brightness at 25%, set color at (145, 75)"
    assert acc.char_brightness.value == 25


@pytest.mark.parametrize(
    ("supported_color_modes", "state_props", "turn_on_props_with_brightness"),
    [
        (
            [ColorMode.RGBW],
            {
                ATTR_RGBW_COLOR: (128, 50, 0, 255),
                ATTR_RGB_COLOR: (128, 50, 0),
                ATTR_HS_COLOR: (23.438, 100.0),
                ATTR_BRIGHTNESS: 255,
                ATTR_COLOR_MODE: ColorMode.RGBW,
            },
            {ATTR_RGBW_COLOR: (0, 0, 0, 191)},
        ),
        (
            [ColorMode.RGBWW],
            {
                ATTR_RGBWW_COLOR: (128, 50, 0, 255, 255),
                ATTR_RGB_COLOR: (128, 50, 0),
                ATTR_HS_COLOR: (23.438, 100.0),
                ATTR_BRIGHTNESS: 255,
                ATTR_COLOR_MODE: ColorMode.RGBWW,
            },
            {ATTR_RGBWW_COLOR: (0, 0, 0, 165, 26)},
        ),
    ],
)
async def test_light_rgbwx_with_color_temp_and_brightness(
    hass: HomeAssistant,
    hk_driver,
    events: list[Event],
    supported_color_modes,
    state_props,
    turn_on_props_with_brightness,
) -> None:
    """Test lights with RGBW/RGBWW with color temp support and setting brightness."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_COLOR_MODES: supported_color_modes, **state_props},
    )
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_hue.value == 23
    assert acc.char_saturation.value == 100

    acc.run()
    await hass.async_block_till_done()
    assert acc.char_hue.value == 23
    assert acc.char_saturation.value == 100
    assert acc.char_brightness.value == 100

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    char_color_temp_iid = acc.char_color_temp.to_HAP()[HAP_REPR_IID]
    char_brightness_iid = acc.char_brightness.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_color_temp_iid,
                    HAP_REPR_VALUE: 200,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_brightness_iid,
                    HAP_REPR_VALUE: 75,
                },
            ]
        },
        "mock_addr",
    )
    await _wait_for_light_coalesce(hass)
    assert call_turn_on
    assert call_turn_on[-1].data[ATTR_ENTITY_ID] == entity_id
    for k, v in turn_on_props_with_brightness.items():
        assert call_turn_on[-1].data[k] == v
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "brightness at 75%, color temperature at 200"
    assert acc.char_brightness.value == 75


async def test_light_rgb_or_w_lights(
    hass: HomeAssistant,
    hk_driver,
    events: list[Event],
) -> None:
    """Test lights with RGB or W lights."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.RGB, ColorMode.WHITE],
            ATTR_RGBW_COLOR: (128, 50, 0, 255),
            ATTR_RGB_COLOR: (128, 50, 0),
            ATTR_HS_COLOR: (23.438, 100.0),
            ATTR_BRIGHTNESS: 255,
            ATTR_COLOR_MODE: ColorMode.RGB,
        },
    )
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_hue.value == 23
    assert acc.char_saturation.value == 100

    acc.run()
    await hass.async_block_till_done()
    assert acc.char_hue.value == 23
    assert acc.char_saturation.value == 100
    assert acc.char_brightness.value == 100
    assert acc.char_color_temp.value == 153

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    char_hue_iid = acc.char_hue.to_HAP()[HAP_REPR_IID]
    char_saturation_iid = acc.char_saturation.to_HAP()[HAP_REPR_IID]
    char_brightness_iid = acc.char_brightness.to_HAP()[HAP_REPR_IID]
    char_color_temp_iid = acc.char_color_temp.to_HAP()[HAP_REPR_IID]

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
    await _wait_for_light_coalesce(hass)
    assert call_turn_on
    assert call_turn_on[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[-1].data[ATTR_HS_COLOR] == (145, 75)
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "set color at (145, 75)"
    assert acc.char_brightness.value == 100

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_color_temp_iid,
                    HAP_REPR_VALUE: acc.min_mireds,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_brightness_iid,
                    HAP_REPR_VALUE: 25,
                },
            ]
        },
        "mock_addr",
    )
    await _wait_for_light_coalesce(hass)
    assert call_turn_on
    assert call_turn_on[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[-1].data[ATTR_WHITE] == round(25 * 255 / 100)
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == "brightness at 25%, color temperature at 153"
    assert acc.char_brightness.value == 25

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.RGB, ColorMode.WHITE],
            ATTR_BRIGHTNESS: 255,
            ATTR_COLOR_MODE: ColorMode.WHITE,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_hue.value == 0
    assert acc.char_saturation.value == 0
    assert acc.char_brightness.value == 100
    assert acc.char_color_temp.value == 153


@pytest.mark.parametrize(
    ("supported_color_modes", "state_props"),
    [
        (
            [ColorMode.COLOR_TEMP, ColorMode.RGBW],
            {
                ATTR_RGBW_COLOR: (128, 50, 0, 255),
                ATTR_RGB_COLOR: (128, 50, 0),
                ATTR_HS_COLOR: (23.438, 100.0),
                ATTR_BRIGHTNESS: 255,
                ATTR_COLOR_MODE: ColorMode.RGBW,
            },
        ),
        (
            [ColorMode.COLOR_TEMP, ColorMode.RGBWW],
            {
                ATTR_RGBWW_COLOR: (128, 50, 0, 255, 255),
                ATTR_RGB_COLOR: (128, 50, 0),
                ATTR_HS_COLOR: (23.438, 100.0),
                ATTR_BRIGHTNESS: 255,
                ATTR_COLOR_MODE: ColorMode.RGBWW,
            },
        ),
    ],
)
async def test_light_rgb_with_white_switch_to_temp(
    hass: HomeAssistant,
    hk_driver,
    events: list[Event],
    supported_color_modes,
    state_props,
) -> None:
    """Test lights with RGBW/RGBWW that preserves brightness when switching to color temp."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_COLOR_MODES: supported_color_modes, **state_props},
    )
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_hue.value == 23
    assert acc.char_saturation.value == 100

    acc.run()
    await hass.async_block_till_done()
    assert acc.char_hue.value == 23
    assert acc.char_saturation.value == 100
    assert acc.char_brightness.value == 100

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    char_hue_iid = acc.char_hue.to_HAP()[HAP_REPR_IID]
    char_saturation_iid = acc.char_saturation.to_HAP()[HAP_REPR_IID]
    char_color_temp_iid = acc.char_color_temp.to_HAP()[HAP_REPR_IID]

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
    await _wait_for_light_coalesce(hass)
    assert call_turn_on
    assert call_turn_on[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[-1].data[ATTR_HS_COLOR] == (145, 75)
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "set color at (145, 75)"
    assert acc.char_brightness.value == 100
    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_color_temp_iid,
                    HAP_REPR_VALUE: 500,
                },
            ]
        },
        "mock_addr",
    )
    await _wait_for_light_coalesce(hass)
    assert call_turn_on
    assert call_turn_on[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[-1].data[ATTR_COLOR_TEMP_KELVIN] == 2000
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == "color temperature at 500"
    assert acc.char_brightness.value == 100


async def test_light_rgb_with_hs_color_none(hass: HomeAssistant, hk_driver) -> None:
    """Test lights hs color set to None."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.RGB],
            ATTR_RGBWW_COLOR: (128, 50, 0, 255, 255),
            ATTR_RGB_COLOR: (128, 50, 0),
            ATTR_HS_COLOR: None,
            ATTR_BRIGHTNESS: 255,
            ATTR_COLOR_MODE: ColorMode.RGB,
        },
    )
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_hue.value == 0
    assert acc.char_saturation.value == 75

    acc.run()
    await hass.async_block_till_done()
    assert acc.char_hue.value == 0
    assert acc.char_saturation.value == 75
    assert acc.char_brightness.value == 100


async def test_light_rgbww_with_color_temp_conversion(
    hass: HomeAssistant,
    hk_driver,
    events: list[Event],
) -> None:
    """Test lights with RGBWW convert color temp as expected."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.RGBWW],
            ATTR_RGBWW_COLOR: (128, 50, 0, 255, 255),
            ATTR_RGB_COLOR: (128, 50, 0),
            ATTR_HS_COLOR: (23.438, 100.0),
            ATTR_BRIGHTNESS: 255,
            ATTR_COLOR_MODE: ColorMode.RGBWW,
        },
    )
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_hue.value == 23
    assert acc.char_saturation.value == 100

    acc.run()
    await hass.async_block_till_done()
    assert acc.char_hue.value == 23
    assert acc.char_saturation.value == 100
    assert acc.char_brightness.value == 100

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    char_hue_iid = acc.char_hue.to_HAP()[HAP_REPR_IID]
    char_saturation_iid = acc.char_saturation.to_HAP()[HAP_REPR_IID]
    char_color_temp_iid = acc.char_color_temp.to_HAP()[HAP_REPR_IID]
    char_brightness_iid = acc.char_brightness.to_HAP()[HAP_REPR_IID]

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
    await _wait_for_light_coalesce(hass)
    assert call_turn_on
    assert call_turn_on[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[-1].data[ATTR_HS_COLOR] == (145, 75)
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "set color at (145, 75)"
    assert acc.char_brightness.value == 100

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_color_temp_iid,
                    HAP_REPR_VALUE: 200,
                },
            ]
        },
        "mock_addr",
    )
    await _wait_for_light_coalesce(hass)
    assert call_turn_on
    assert call_turn_on[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[-1].data[ATTR_RGBWW_COLOR] == (0, 0, 0, 220, 35)
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == "color temperature at 200"
    assert acc.char_brightness.value == 100

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.RGBWW],
            ATTR_RGBWW_COLOR: (0, 0, 0, 128, 255),
            ATTR_RGB_COLOR: (255, 163, 79),
            ATTR_HS_COLOR: (28.636, 69.02),
            ATTR_BRIGHTNESS: 180,
            ATTR_COLOR_MODE: ColorMode.RGBWW,
        },
    )
    await hass.async_block_till_done()

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_brightness_iid,
                    HAP_REPR_VALUE: 100,
                },
            ]
        },
        "mock_addr",
    )
    await _wait_for_light_coalesce(hass)
    assert call_turn_on
    assert call_turn_on[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[-1].data[ATTR_BRIGHTNESS_PCT] == 100
    assert len(events) == 3
    assert events[-1].data[ATTR_VALUE] == "brightness at 100%"
    assert acc.char_brightness.value == 100


async def test_light_rgbw_with_color_temp_conversion(
    hass: HomeAssistant,
    hk_driver,
    events: list[Event],
) -> None:
    """Test lights with RGBW convert color temp as expected."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.RGBW],
            ATTR_RGBWW_COLOR: (128, 50, 0, 255, 255),
            ATTR_RGB_COLOR: (128, 50, 0),
            ATTR_HS_COLOR: (23.438, 100.0),
            ATTR_BRIGHTNESS: 255,
            ATTR_COLOR_MODE: ColorMode.RGBW,
        },
    )
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_hue.value == 23
    assert acc.char_saturation.value == 100

    acc.run()
    await hass.async_block_till_done()
    assert acc.char_hue.value == 23
    assert acc.char_saturation.value == 100
    assert acc.char_brightness.value == 100

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    char_hue_iid = acc.char_hue.to_HAP()[HAP_REPR_IID]
    char_saturation_iid = acc.char_saturation.to_HAP()[HAP_REPR_IID]
    char_color_temp_iid = acc.char_color_temp.to_HAP()[HAP_REPR_IID]
    assert (
        acc.char_color_temp.properties[PROP_MIN_VALUE]
        == acc.char_color_temp.properties[PROP_MAX_VALUE]
    )

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
    await _wait_for_light_coalesce(hass)
    assert call_turn_on
    assert call_turn_on[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[-1].data[ATTR_HS_COLOR] == (145, 75)
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "set color at (145, 75)"
    assert acc.char_brightness.value == 100

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_color_temp_iid,
                    HAP_REPR_VALUE: 153,
                },
            ]
        },
        "mock_addr",
    )
    await _wait_for_light_coalesce(hass)
    assert call_turn_on
    assert call_turn_on[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[-1].data[ATTR_RGBW_COLOR] == (0, 0, 0, 255)
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == "color temperature at 153"
    assert acc.char_brightness.value == 100


async def test_light_set_brightness_and_color(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test light with all chars in one go."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS],
            ATTR_BRIGHTNESS: 255,
        },
    )
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    # Initial value can be anything but 0. If it is 0, it might cause HomeKit to set the
    # brightness to 100 when turning on a light on a freshly booted up server.
    assert acc.char_brightness.value != 0
    char_on_iid = acc.char_on.to_HAP()[HAP_REPR_IID]
    char_brightness_iid = acc.char_brightness.to_HAP()[HAP_REPR_IID]
    char_hue_iid = acc.char_hue.to_HAP()[HAP_REPR_IID]
    char_saturation_iid = acc.char_saturation.to_HAP()[HAP_REPR_IID]

    acc.run()
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 100

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS], ATTR_BRIGHTNESS: 102},
    )
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 40

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS], ATTR_HS_COLOR: (4.5, 9.2)},
    )
    await hass.async_block_till_done()
    assert acc.char_hue.value == 4
    assert acc.char_saturation.value == 9

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

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
    await _wait_for_light_coalesce(hass)
    assert call_turn_on[0]
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[0].data[ATTR_BRIGHTNESS_PCT] == 20
    assert call_turn_on[0].data[ATTR_HS_COLOR] == (145, 75)

    assert len(events) == 1
    assert (
        events[-1].data[ATTR_VALUE]
        == f"Set state to 1, brightness at 20{PERCENTAGE}, set color at (145, 75)"
    )


async def test_light_min_max_mireds(hass: HomeAssistant, hk_driver) -> None:
    """Test mireds are forced to ints."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP],
            ATTR_BRIGHTNESS: 255,
            ATTR_MIN_COLOR_TEMP_KELVIN: 1999,
            ATTR_MAX_COLOR_TEMP_KELVIN: 6499,
        },
    )
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", entity_id, 1, None)
    assert acc.char_color_temp.properties["maxValue"] == 500
    assert acc.char_color_temp.properties["minValue"] == 153


async def test_light_set_brightness_and_color_temp(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test light with all chars in one go."""
    entity_id = "light.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP],
            ATTR_BRIGHTNESS: 255,
        },
    )
    await hass.async_block_till_done()
    acc = Light(hass, hk_driver, "Light", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    # Initial value can be anything but 0. If it is 0, it might cause HomeKit to set the
    # brightness to 100 when turning on a light on a freshly booted up server.
    assert acc.char_brightness.value != 0
    char_on_iid = acc.char_on.to_HAP()[HAP_REPR_IID]
    char_brightness_iid = acc.char_brightness.to_HAP()[HAP_REPR_IID]
    char_color_temp_iid = acc.char_color_temp.to_HAP()[HAP_REPR_IID]

    acc.run()
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 100

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP], ATTR_BRIGHTNESS: 102},
    )
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 40

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP],
            ATTR_COLOR_TEMP_KELVIN: (4461),
        },
    )
    await hass.async_block_till_done()
    assert acc.char_color_temp.value == 224

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

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
                    HAP_REPR_IID: char_color_temp_iid,
                    HAP_REPR_VALUE: 250,
                },
            ]
        },
        "mock_addr",
    )
    await _wait_for_light_coalesce(hass)
    assert call_turn_on[0]
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[0].data[ATTR_BRIGHTNESS_PCT] == 20
    assert call_turn_on[0].data[ATTR_COLOR_TEMP_KELVIN] == 4000

    assert len(events) == 1
    assert (
        events[-1].data[ATTR_VALUE]
        == f"Set state to 1, brightness at 20{PERCENTAGE}, color temperature at 250"
    )
