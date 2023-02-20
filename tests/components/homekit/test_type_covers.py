"""Test different accessory types: Covers."""
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN,
    CoverEntityFeature,
)
from homeassistant.components.homekit.const import (
    ATTR_OBSTRUCTION_DETECTED,
    ATTR_VALUE,
    CONF_LINKED_OBSTRUCTION_SENSOR,
    HK_DOOR_CLOSED,
    HK_DOOR_CLOSING,
    HK_DOOR_OPEN,
    HK_DOOR_OPENING,
    PROP_MAX_VALUE,
    PROP_MIN_VALUE,
)
from homeassistant.components.homekit.type_covers import (
    GarageDoorOpener,
    Window,
    WindowCovering,
    WindowCoveringBasic,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    EVENT_HOMEASSISTANT_START,
    SERVICE_SET_COVER_TILT_POSITION,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import async_mock_service


async def test_garage_door_open_close(hass: HomeAssistant, hk_driver, events) -> None:
    """Test if accessory and HA are updated accordingly."""
    entity_id = "cover.garage_door"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = GarageDoorOpener(hass, hk_driver, "Garage Door", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 4  # GarageDoorOpener

    assert acc.char_current_state.value == HK_DOOR_OPEN
    assert acc.char_target_state.value == HK_DOOR_OPEN

    hass.states.async_set(entity_id, STATE_CLOSED, {ATTR_OBSTRUCTION_DETECTED: False})
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HK_DOOR_CLOSED
    assert acc.char_target_state.value == HK_DOOR_CLOSED
    assert acc.char_obstruction_detected.value is False

    hass.states.async_set(entity_id, STATE_OPEN, {ATTR_OBSTRUCTION_DETECTED: True})
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HK_DOOR_OPEN
    assert acc.char_target_state.value == HK_DOOR_OPEN
    assert acc.char_obstruction_detected.value is True

    hass.states.async_set(
        entity_id, STATE_UNAVAILABLE, {ATTR_OBSTRUCTION_DETECTED: False}
    )
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HK_DOOR_OPEN
    assert acc.char_target_state.value == HK_DOOR_OPEN
    assert acc.char_obstruction_detected.value is False

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HK_DOOR_OPEN
    assert acc.char_target_state.value == HK_DOOR_OPEN

    # Set from HomeKit
    call_close_cover = async_mock_service(hass, DOMAIN, "close_cover")
    call_open_cover = async_mock_service(hass, DOMAIN, "open_cover")

    acc.char_target_state.client_update_value(1)
    await hass.async_block_till_done()
    assert call_close_cover
    assert call_close_cover[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_current_state.value == HK_DOOR_CLOSING
    assert acc.char_target_state.value == HK_DOOR_CLOSED
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    hass.states.async_set(entity_id, STATE_CLOSED)
    await hass.async_block_till_done()

    acc.char_target_state.client_update_value(1)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HK_DOOR_CLOSED
    assert acc.char_target_state.value == HK_DOOR_CLOSED
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_target_state.client_update_value(0)
    await hass.async_block_till_done()
    assert call_open_cover
    assert call_open_cover[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_current_state.value == HK_DOOR_OPENING
    assert acc.char_target_state.value == HK_DOOR_OPEN
    assert len(events) == 3
    assert events[-1].data[ATTR_VALUE] is None

    hass.states.async_set(entity_id, STATE_OPEN)
    await hass.async_block_till_done()

    acc.char_target_state.client_update_value(0)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HK_DOOR_OPEN
    assert acc.char_target_state.value == HK_DOOR_OPEN
    assert len(events) == 4
    assert events[-1].data[ATTR_VALUE] is None


async def test_windowcovering_set_cover_position(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test if accessory and HA are updated accordingly."""
    entity_id = "cover.window"

    hass.states.async_set(
        entity_id,
        STATE_UNKNOWN,
        {ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION},
    )
    await hass.async_block_till_done()
    acc = WindowCovering(hass, hk_driver, "Cover", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 14  # WindowCovering

    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0

    hass.states.async_set(
        entity_id,
        STATE_UNKNOWN,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
            ATTR_CURRENT_POSITION: None,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0
    assert acc.char_position_state.value == 2

    hass.states.async_set(
        entity_id,
        STATE_OPENING,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
            ATTR_CURRENT_POSITION: 60,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 60
    assert acc.char_target_position.value == 0
    assert acc.char_position_state.value == 1

    hass.states.async_set(
        entity_id,
        STATE_OPENING,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
            ATTR_CURRENT_POSITION: 70.0,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 70
    assert acc.char_target_position.value == 0
    assert acc.char_position_state.value == 1

    hass.states.async_set(
        entity_id,
        STATE_CLOSING,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
            ATTR_CURRENT_POSITION: 50,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 50
    assert acc.char_target_position.value == 0
    assert acc.char_position_state.value == 0

    hass.states.async_set(
        entity_id,
        STATE_OPEN,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
            ATTR_CURRENT_POSITION: 50,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 50
    assert acc.char_target_position.value == 50
    assert acc.char_position_state.value == 2

    # Set from HomeKit
    call_set_cover_position = async_mock_service(hass, DOMAIN, "set_cover_position")

    acc.char_target_position.client_update_value(25)
    await hass.async_block_till_done()
    assert call_set_cover_position[0]
    assert call_set_cover_position[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_cover_position[0].data[ATTR_POSITION] == 25
    assert acc.char_current_position.value == 50
    assert acc.char_target_position.value == 25
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == 25

    acc.char_target_position.client_update_value(75)
    await hass.async_block_till_done()
    assert call_set_cover_position[1]
    assert call_set_cover_position[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_cover_position[1].data[ATTR_POSITION] == 75
    assert acc.char_current_position.value == 50
    assert acc.char_target_position.value == 75
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == 75


async def test_window_instantiate_set_position(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test if Window accessory is instantiated correctly and can set position."""
    entity_id = "cover.window"

    hass.states.async_set(
        entity_id,
        STATE_OPEN,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
            ATTR_CURRENT_POSITION: 0,
        },
    )
    await hass.async_block_till_done()
    acc = Window(hass, hk_driver, "Window", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 13  # Window

    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0

    hass.states.async_set(
        entity_id,
        STATE_OPEN,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
            ATTR_CURRENT_POSITION: 50,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 50
    assert acc.char_target_position.value == 50
    assert acc.char_position_state.value == 2

    hass.states.async_set(
        entity_id,
        STATE_OPEN,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
            ATTR_CURRENT_POSITION: "GARBAGE",
        },
    )
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 50
    assert acc.char_target_position.value == 50
    assert acc.char_position_state.value == 2


async def test_windowcovering_cover_set_tilt(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test if accessory and HA update slat tilt accordingly."""
    entity_id = "cover.window"

    hass.states.async_set(
        entity_id,
        STATE_UNKNOWN,
        {ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_TILT_POSITION},
    )
    await hass.async_block_till_done()
    acc = WindowCovering(hass, hk_driver, "Cover", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 14  # CATEGORY_WINDOW_COVERING

    assert acc.char_current_tilt.value == 0
    assert acc.char_target_tilt.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN, {ATTR_CURRENT_TILT_POSITION: None})
    await hass.async_block_till_done()
    assert acc.char_current_tilt.value == 0
    assert acc.char_target_tilt.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN, {ATTR_CURRENT_TILT_POSITION: 100})
    await hass.async_block_till_done()
    assert acc.char_current_tilt.value == 90
    assert acc.char_target_tilt.value == 90

    hass.states.async_set(entity_id, STATE_UNKNOWN, {ATTR_CURRENT_TILT_POSITION: 50})
    await hass.async_block_till_done()
    assert acc.char_current_tilt.value == 0
    assert acc.char_target_tilt.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN, {ATTR_CURRENT_TILT_POSITION: 0})
    await hass.async_block_till_done()
    assert acc.char_current_tilt.value == -90
    assert acc.char_target_tilt.value == -90

    # set from HomeKit
    call_set_tilt_position = async_mock_service(
        hass, DOMAIN, SERVICE_SET_COVER_TILT_POSITION
    )

    # HomeKit sets tilts between -90 and 90 (degrees), whereas
    # Homeassistant expects a % between 0 and 100. Keep that in mind
    # when comparing
    acc.char_target_tilt.client_update_value(90)
    await hass.async_block_till_done()
    assert call_set_tilt_position[0]
    assert call_set_tilt_position[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_tilt_position[0].data[ATTR_TILT_POSITION] == 100
    assert acc.char_current_tilt.value == -90
    assert acc.char_target_tilt.value == 90
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == 100

    acc.char_target_tilt.client_update_value(45)
    await hass.async_block_till_done()
    assert call_set_tilt_position[1]
    assert call_set_tilt_position[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_tilt_position[1].data[ATTR_TILT_POSITION] == 75
    assert acc.char_current_tilt.value == -90
    assert acc.char_target_tilt.value == 45
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == 75


async def test_windowcovering_tilt_only(hass: HomeAssistant, hk_driver, events) -> None:
    """Test we lock the window covering closed when its tilt only."""
    entity_id = "cover.window"

    hass.states.async_set(
        entity_id,
        STATE_UNKNOWN,
        {ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_TILT_POSITION},
    )
    await hass.async_block_till_done()
    acc = WindowCovering(hass, hk_driver, "Cover", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 14  # WindowCovering

    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0
    assert acc.char_target_position.properties[PROP_MIN_VALUE] == 0
    assert acc.char_target_position.properties[PROP_MAX_VALUE] == 0


async def test_windowcovering_open_close(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test if accessory and HA are updated accordingly."""
    entity_id = "cover.window"

    hass.states.async_set(entity_id, STATE_UNKNOWN, {ATTR_SUPPORTED_FEATURES: 0})
    acc = WindowCoveringBasic(hass, hk_driver, "Cover", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 14  # WindowCovering

    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0
    assert acc.char_position_state.value == 2

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0
    assert acc.char_position_state.value == 2

    hass.states.async_set(entity_id, STATE_OPENING)
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0
    assert acc.char_position_state.value == 1

    hass.states.async_set(entity_id, STATE_OPEN)
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 100
    assert acc.char_target_position.value == 100
    assert acc.char_position_state.value == 2

    hass.states.async_set(entity_id, STATE_CLOSING)
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 100
    assert acc.char_target_position.value == 100
    assert acc.char_position_state.value == 0

    hass.states.async_set(entity_id, STATE_CLOSED)
    await hass.async_block_till_done()
    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0
    assert acc.char_position_state.value == 2

    # Set from HomeKit
    call_close_cover = async_mock_service(hass, DOMAIN, "close_cover")
    call_open_cover = async_mock_service(hass, DOMAIN, "open_cover")

    acc.char_target_position.client_update_value(25)
    await hass.async_block_till_done()
    assert call_close_cover
    assert call_close_cover[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0
    assert acc.char_position_state.value == 2
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_target_position.client_update_value(90)
    await hass.async_block_till_done()
    assert call_open_cover[0]
    assert call_open_cover[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_current_position.value == 100
    assert acc.char_target_position.value == 100
    assert acc.char_position_state.value == 2
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_target_position.client_update_value(55)
    await hass.async_block_till_done()
    assert call_open_cover[1]
    assert call_open_cover[1].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_current_position.value == 100
    assert acc.char_target_position.value == 100
    assert acc.char_position_state.value == 2
    assert len(events) == 3
    assert events[-1].data[ATTR_VALUE] is None


async def test_windowcovering_open_close_stop(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test if accessory and HA are updated accordingly."""
    entity_id = "cover.window"

    hass.states.async_set(
        entity_id, STATE_UNKNOWN, {ATTR_SUPPORTED_FEATURES: CoverEntityFeature.STOP}
    )
    acc = WindowCoveringBasic(hass, hk_driver, "Cover", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    # Set from HomeKit
    call_close_cover = async_mock_service(hass, DOMAIN, "close_cover")
    call_open_cover = async_mock_service(hass, DOMAIN, "open_cover")
    call_stop_cover = async_mock_service(hass, DOMAIN, "stop_cover")

    acc.char_target_position.client_update_value(25)
    await hass.async_block_till_done()
    assert call_close_cover
    assert call_close_cover[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_current_position.value == 0
    assert acc.char_target_position.value == 0
    assert acc.char_position_state.value == 2
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_target_position.client_update_value(90)
    await hass.async_block_till_done()
    assert call_open_cover
    assert call_open_cover[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_current_position.value == 100
    assert acc.char_target_position.value == 100
    assert acc.char_position_state.value == 2
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_target_position.client_update_value(55)
    await hass.async_block_till_done()
    assert call_stop_cover
    assert call_stop_cover[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_current_position.value == 50
    assert acc.char_target_position.value == 50
    assert acc.char_position_state.value == 2
    assert len(events) == 3
    assert events[-1].data[ATTR_VALUE] is None


async def test_windowcovering_open_close_with_position_and_stop(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test if accessory and HA are updated accordingly."""
    entity_id = "cover.stop_window"

    hass.states.async_set(
        entity_id,
        STATE_UNKNOWN,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        },
    )
    acc = WindowCovering(hass, hk_driver, "Cover", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    # Set from HomeKit
    call_stop_cover = async_mock_service(hass, DOMAIN, "stop_cover")

    acc.char_hold_position.client_update_value(0)
    await hass.async_block_till_done()
    assert not call_stop_cover

    acc.char_hold_position.client_update_value(1)
    await hass.async_block_till_done()
    assert call_stop_cover
    assert call_stop_cover[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_hold_position.value == 1
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None


async def test_windowcovering_basic_restore(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test setting up an entity from state in the event registry."""
    hass.state = CoreState.not_running

    registry = er.async_get(hass)

    registry.async_get_or_create(
        "cover",
        "generic",
        "1234",
        suggested_object_id="simple",
    )
    registry.async_get_or_create(
        "cover",
        "generic",
        "9012",
        suggested_object_id="all_info_set",
        capabilities={},
        supported_features=CoverEntityFeature.STOP,
        original_device_class="mock-device-class",
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START, {})
    await hass.async_block_till_done()

    acc = WindowCoveringBasic(hass, hk_driver, "Cover", "cover.simple", 2, None)
    assert acc.category == 14
    assert acc.char_current_position is not None
    assert acc.char_target_position is not None
    assert acc.char_position_state is not None

    acc = WindowCoveringBasic(hass, hk_driver, "Cover", "cover.all_info_set", 3, None)
    assert acc.category == 14
    assert acc.char_current_position is not None
    assert acc.char_target_position is not None
    assert acc.char_position_state is not None


async def test_windowcovering_restore(hass: HomeAssistant, hk_driver, events) -> None:
    """Test setting up an entity from state in the event registry."""
    hass.state = CoreState.not_running

    registry = er.async_get(hass)

    registry.async_get_or_create(
        "cover",
        "generic",
        "1234",
        suggested_object_id="simple",
    )
    registry.async_get_or_create(
        "cover",
        "generic",
        "9012",
        suggested_object_id="all_info_set",
        capabilities={},
        supported_features=CoverEntityFeature.STOP,
        original_device_class="mock-device-class",
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START, {})
    await hass.async_block_till_done()

    acc = WindowCovering(hass, hk_driver, "Cover", "cover.simple", 2, None)
    assert acc.category == 14
    assert acc.char_current_position is not None
    assert acc.char_target_position is not None
    assert acc.char_position_state is not None

    acc = WindowCovering(hass, hk_driver, "Cover", "cover.all_info_set", 3, None)
    assert acc.category == 14
    assert acc.char_current_position is not None
    assert acc.char_target_position is not None
    assert acc.char_position_state is not None


async def test_garage_door_with_linked_obstruction_sensor(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test if accessory and HA are updated accordingly with a linked obstruction sensor."""
    linked_obstruction_sensor_entity_id = "binary_sensor.obstruction"
    entity_id = "cover.garage_door"

    hass.states.async_set(linked_obstruction_sensor_entity_id, STATE_OFF)
    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = GarageDoorOpener(
        hass,
        hk_driver,
        "Garage Door",
        entity_id,
        2,
        {CONF_LINKED_OBSTRUCTION_SENSOR: linked_obstruction_sensor_entity_id},
    )
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 4  # GarageDoorOpener

    assert acc.char_current_state.value == HK_DOOR_OPEN
    assert acc.char_target_state.value == HK_DOOR_OPEN

    hass.states.async_set(entity_id, STATE_CLOSED)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HK_DOOR_CLOSED
    assert acc.char_target_state.value == HK_DOOR_CLOSED
    assert acc.char_obstruction_detected.value is False

    hass.states.async_set(entity_id, STATE_OPEN)
    hass.states.async_set(linked_obstruction_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HK_DOOR_OPEN
    assert acc.char_target_state.value == HK_DOOR_OPEN
    assert acc.char_obstruction_detected.value is True

    hass.states.async_set(entity_id, STATE_CLOSED)
    hass.states.async_set(linked_obstruction_sensor_entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HK_DOOR_CLOSED
    assert acc.char_target_state.value == HK_DOOR_CLOSED
    assert acc.char_obstruction_detected.value is False

    hass.states.async_remove(entity_id)
    hass.states.async_remove(linked_obstruction_sensor_entity_id)
    await hass.async_block_till_done()
