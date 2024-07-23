"""Test different accessory types: Fans."""

from pyhap.const import HAP_REPR_AID, HAP_REPR_CHARS, HAP_REPR_IID, HAP_REPR_VALUE

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PERCENTAGE_STEP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN,
    FanEntityFeature,
)
from homeassistant.components.homekit.const import ATTR_VALUE, PROP_MIN_STEP
from homeassistant.components.homekit.type_fans import Fan
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    EVENT_HOMEASSISTANT_START,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import async_mock_service


async def test_fan_basic(hass: HomeAssistant, hk_driver, events) -> None:
    """Test fan with char state."""
    entity_id = "fan.demo"

    hass.states.async_set(entity_id, STATE_ON, {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    acc = Fan(hass, hk_driver, "Fan", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.aid == 1
    assert acc.category == 3  # Fan
    assert acc.char_active.value == 1

    # If there are no speed_list values, then HomeKit speed is unsupported
    assert acc.char_speed is None

    acc.run()
    await hass.async_block_till_done()
    assert acc.char_active.value == 1

    hass.states.async_set(entity_id, STATE_OFF, {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, "turn_on")
    call_turn_off = async_mock_service(hass, DOMAIN, "turn_off")

    char_active_iid = acc.char_active.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_active_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_active_iid,
                    HAP_REPR_VALUE: 0,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


async def test_fan_direction(hass: HomeAssistant, hk_driver, events) -> None:
    """Test fan with direction."""
    entity_id = "fan.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.DIRECTION,
            ATTR_DIRECTION: DIRECTION_FORWARD,
        },
    )
    await hass.async_block_till_done()
    acc = Fan(hass, hk_driver, "Fan", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_direction.value == 0

    acc.run()
    await hass.async_block_till_done()
    assert acc.char_direction.value == 0

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.DIRECTION,
            ATTR_DIRECTION: DIRECTION_REVERSE,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_direction.value == 1

    # Set from HomeKit
    call_set_direction = async_mock_service(hass, DOMAIN, "set_direction")

    char_direction_iid = acc.char_direction.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_direction_iid,
                    HAP_REPR_VALUE: 0,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_set_direction[0]
    assert call_set_direction[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_direction[0].data[ATTR_DIRECTION] == DIRECTION_FORWARD
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == DIRECTION_FORWARD

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_direction_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    acc.char_direction.client_update_value(1)
    await hass.async_block_till_done()
    assert call_set_direction[1]
    assert call_set_direction[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_direction[1].data[ATTR_DIRECTION] == DIRECTION_REVERSE
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == DIRECTION_REVERSE


async def test_fan_oscillate(hass: HomeAssistant, hk_driver, events) -> None:
    """Test fan with oscillate."""
    entity_id = "fan.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_FEATURES: FanEntityFeature.OSCILLATE, ATTR_OSCILLATING: False},
    )
    await hass.async_block_till_done()
    acc = Fan(hass, hk_driver, "Fan", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_swing.value == 0

    acc.run()
    await hass.async_block_till_done()
    assert acc.char_swing.value == 0

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_FEATURES: FanEntityFeature.OSCILLATE, ATTR_OSCILLATING: True},
    )
    await hass.async_block_till_done()
    assert acc.char_swing.value == 1

    # Set from HomeKit
    call_oscillate = async_mock_service(hass, DOMAIN, "oscillate")

    char_swing_iid = acc.char_swing.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_swing_iid,
                    HAP_REPR_VALUE: 0,
                },
            ]
        },
        "mock_addr",
    )
    acc.char_swing.client_update_value(0)
    await hass.async_block_till_done()
    assert call_oscillate[0]
    assert call_oscillate[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_oscillate[0].data[ATTR_OSCILLATING] is False
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is False

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_swing_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    acc.char_swing.client_update_value(1)
    await hass.async_block_till_done()
    assert call_oscillate[1]
    assert call_oscillate[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_oscillate[1].data[ATTR_OSCILLATING] is True
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is True


async def test_fan_speed(hass: HomeAssistant, hk_driver, events) -> None:
    """Test fan with speed."""
    entity_id = "fan.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.SET_SPEED,
            ATTR_PERCENTAGE: 0,
            ATTR_PERCENTAGE_STEP: 25,
        },
    )
    await hass.async_block_till_done()
    acc = Fan(hass, hk_driver, "Fan", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    # Initial value can be anything but 0. If it is 0, it might cause HomeKit to set the
    # speed to 100 when turning on a fan on a freshly booted up server.
    assert acc.char_speed.value != 0
    assert acc.char_speed.properties[PROP_MIN_STEP] == 25

    acc.run()
    await hass.async_block_till_done()

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_PERCENTAGE_STEP: 25,
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.SET_SPEED,
            ATTR_PERCENTAGE: 100,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_speed.value == 100

    # Set from HomeKit
    call_set_percentage = async_mock_service(hass, DOMAIN, "set_percentage")

    char_speed_iid = acc.char_speed.to_HAP()[HAP_REPR_IID]
    char_active_iid = acc.char_active.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_speed_iid,
                    HAP_REPR_VALUE: 42,
                },
            ]
        },
        "mock_addr",
    )
    acc.char_speed.client_update_value(42)
    await hass.async_block_till_done()
    assert acc.char_speed.value == 50
    assert acc.char_active.value == 1

    assert call_set_percentage[0]
    assert call_set_percentage[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_percentage[0].data[ATTR_PERCENTAGE] == 42
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == 42

    # Verify speed is preserved from off to on
    hass.states.async_set(
        entity_id,
        STATE_OFF,
        {
            ATTR_PERCENTAGE_STEP: 25,
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.SET_SPEED,
            ATTR_PERCENTAGE: 42,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_speed.value == 50
    assert acc.char_active.value == 0

    call_turn_on = async_mock_service(hass, DOMAIN, "turn_on")

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_active_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert acc.char_speed.value == 50
    assert acc.char_active.value == 1

    assert call_turn_on[0]
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id


async def test_fan_set_all_one_shot(hass: HomeAssistant, hk_driver, events) -> None:
    """Test fan with speed."""
    entity_id = "fan.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.SET_SPEED
            | FanEntityFeature.OSCILLATE
            | FanEntityFeature.DIRECTION,
            ATTR_PERCENTAGE: 0,
            ATTR_OSCILLATING: False,
            ATTR_DIRECTION: DIRECTION_FORWARD,
        },
    )
    await hass.async_block_till_done()
    acc = Fan(hass, hk_driver, "Fan", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    # Initial value can be anything but 0. If it is 0, it might cause HomeKit to set the
    # speed to 100 when turning on a fan on a freshly booted up server.
    assert acc.char_speed.value != 0
    acc.run()
    await hass.async_block_till_done()

    hass.states.async_set(
        entity_id,
        STATE_OFF,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.SET_SPEED
            | FanEntityFeature.OSCILLATE
            | FanEntityFeature.DIRECTION,
            ATTR_PERCENTAGE: 0,
            ATTR_OSCILLATING: False,
            ATTR_DIRECTION: DIRECTION_FORWARD,
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    # Set from HomeKit
    call_set_percentage = async_mock_service(hass, DOMAIN, "set_percentage")
    call_oscillate = async_mock_service(hass, DOMAIN, "oscillate")
    call_set_direction = async_mock_service(hass, DOMAIN, "set_direction")
    call_turn_on = async_mock_service(hass, DOMAIN, "turn_on")
    call_turn_off = async_mock_service(hass, DOMAIN, "turn_off")

    char_active_iid = acc.char_active.to_HAP()[HAP_REPR_IID]
    char_direction_iid = acc.char_direction.to_HAP()[HAP_REPR_IID]
    char_swing_iid = acc.char_swing.to_HAP()[HAP_REPR_IID]
    char_speed_iid = acc.char_speed.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_active_iid,
                    HAP_REPR_VALUE: 1,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_speed_iid,
                    HAP_REPR_VALUE: 42,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_swing_iid,
                    HAP_REPR_VALUE: 1,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_direction_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert not call_turn_on
    assert call_set_percentage[0]
    assert call_set_percentage[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_percentage[0].data[ATTR_PERCENTAGE] == 42
    assert call_oscillate[0]
    assert call_oscillate[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_oscillate[0].data[ATTR_OSCILLATING] is True
    assert call_set_direction[0]
    assert call_set_direction[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_direction[0].data[ATTR_DIRECTION] == DIRECTION_REVERSE
    assert len(events) == 3

    assert events[0].data[ATTR_VALUE] is True
    assert events[1].data[ATTR_VALUE] == DIRECTION_REVERSE
    assert events[2].data[ATTR_VALUE] == 42

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.SET_SPEED
            | FanEntityFeature.OSCILLATE
            | FanEntityFeature.DIRECTION,
            ATTR_PERCENTAGE: 0,
            ATTR_OSCILLATING: False,
            ATTR_DIRECTION: DIRECTION_FORWARD,
        },
    )
    await hass.async_block_till_done()

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_active_iid,
                    HAP_REPR_VALUE: 1,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_speed_iid,
                    HAP_REPR_VALUE: 42,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_swing_iid,
                    HAP_REPR_VALUE: 1,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_direction_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    # Turn on should not be called if its already on
    # and we set a fan speed
    await hass.async_block_till_done()
    assert len(events) == 6
    assert call_set_percentage[1]
    assert call_set_percentage[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_percentage[1].data[ATTR_PERCENTAGE] == 42
    assert call_oscillate[1]
    assert call_oscillate[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_oscillate[1].data[ATTR_OSCILLATING] is True
    assert call_set_direction[1]
    assert call_set_direction[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_direction[1].data[ATTR_DIRECTION] == DIRECTION_REVERSE

    assert events[-3].data[ATTR_VALUE] is True
    assert events[-2].data[ATTR_VALUE] == DIRECTION_REVERSE
    assert events[-1].data[ATTR_VALUE] == 42

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_active_iid,
                    HAP_REPR_VALUE: 0,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_speed_iid,
                    HAP_REPR_VALUE: 42,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_swing_iid,
                    HAP_REPR_VALUE: 1,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_direction_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()

    assert len(events) == 7
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(call_set_percentage) == 2
    assert len(call_oscillate) == 2
    assert len(call_set_direction) == 2


async def test_fan_restore(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, hk_driver, events
) -> None:
    """Test setting up an entity from state in the event registry."""
    hass.set_state(CoreState.not_running)

    entity_registry.async_get_or_create(
        "fan",
        "generic",
        "1234",
        suggested_object_id="simple",
    )
    entity_registry.async_get_or_create(
        "fan",
        "generic",
        "9012",
        suggested_object_id="all_info_set",
        capabilities={"speed_list": ["off", "low", "medium", "high"]},
        supported_features=FanEntityFeature.SET_SPEED
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.DIRECTION,
        original_device_class="mock-device-class",
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START, {})
    await hass.async_block_till_done()

    acc = Fan(hass, hk_driver, "Fan", "fan.simple", 2, None)
    assert acc.category == 3
    assert acc.char_active is not None
    assert acc.char_direction is None
    assert acc.char_speed is None
    assert acc.char_swing is None

    acc = Fan(hass, hk_driver, "Fan", "fan.all_info_set", 3, None)
    assert acc.category == 3
    assert acc.char_active is not None
    assert acc.char_direction is not None
    assert acc.char_speed is not None
    assert acc.char_swing is not None


async def test_fan_multiple_preset_modes(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test fan with multiple preset modes."""
    entity_id = "fan.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.PRESET_MODE,
            ATTR_PRESET_MODE: "auto",
            ATTR_PRESET_MODES: ["auto", "smart"],
        },
    )
    await hass.async_block_till_done()
    acc = Fan(hass, hk_driver, "Fan", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.preset_mode_chars["auto"].value == 1
    assert acc.preset_mode_chars["smart"].value == 0

    acc.run()
    await hass.async_block_till_done()

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.PRESET_MODE,
            ATTR_PRESET_MODE: "smart",
            ATTR_PRESET_MODES: ["auto", "smart"],
        },
    )
    await hass.async_block_till_done()

    assert acc.preset_mode_chars["auto"].value == 0
    assert acc.preset_mode_chars["smart"].value == 1
    # Set from HomeKit
    call_set_preset_mode = async_mock_service(hass, DOMAIN, "set_preset_mode")
    call_turn_on = async_mock_service(hass, DOMAIN, "turn_on")

    char_auto_iid = acc.preset_mode_chars["auto"].to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_auto_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_set_preset_mode[0]
    assert call_set_preset_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_preset_mode[0].data[ATTR_PRESET_MODE] == "auto"
    assert len(events) == 1
    assert events[-1].data["service"] == "set_preset_mode"

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_auto_iid,
                    HAP_REPR_VALUE: 0,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_turn_on[0]
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert events[-1].data["service"] == "turn_on"
    assert len(events) == 2


async def test_fan_single_preset_mode(hass: HomeAssistant, hk_driver, events) -> None:
    """Test fan with a single preset mode."""
    entity_id = "fan.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED,
            ATTR_PERCENTAGE: 42,
            ATTR_PRESET_MODE: "smart",
            ATTR_PRESET_MODES: ["smart"],
        },
    )
    await hass.async_block_till_done()
    acc = Fan(hass, hk_driver, "Fan", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_target_fan_state.value == 1

    acc.run()
    await hass.async_block_till_done()

    # Set from HomeKit
    call_set_preset_mode = async_mock_service(hass, DOMAIN, "set_preset_mode")
    call_turn_on = async_mock_service(hass, DOMAIN, "turn_on")

    char_target_fan_state_iid = acc.char_target_fan_state.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_fan_state_iid,
                    HAP_REPR_VALUE: 0,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_turn_on[0]
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[0].data[ATTR_PERCENTAGE] == 42
    assert len(events) == 1
    assert events[-1].data["service"] == "turn_on"

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_fan_state_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_set_preset_mode[0]
    assert call_set_preset_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_preset_mode[0].data[ATTR_PRESET_MODE] == "smart"
    assert events[-1].data["service"] == "set_preset_mode"
    assert len(events) == 2

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED,
            ATTR_PERCENTAGE: 42,
            ATTR_PRESET_MODE: None,
            ATTR_PRESET_MODES: ["smart"],
        },
    )
    await hass.async_block_till_done()
    assert acc.char_target_fan_state.value == 0
