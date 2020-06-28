"""Basic checks for HomeKitalarm_control_panel."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from tests.components.homekit_controller.common import setup_test_component

POSITION_STATE = ("window-covering", "position.state")
POSITION_CURRENT = ("window-covering", "position.current")
POSITION_TARGET = ("window-covering", "position.target")
POSITION_HOLD = ("window-covering", "position.hold")

H_TILT_CURRENT = ("window-covering", "horizontal-tilt.current")
H_TILT_TARGET = ("window-covering", "horizontal-tilt.target")

V_TILT_CURRENT = ("window-covering", "vertical-tilt.current")
V_TILT_TARGET = ("window-covering", "vertical-tilt.target")

WINDOW_OBSTRUCTION = ("window-covering", "obstruction-detected")

DOOR_CURRENT = ("garage-door-opener", "door-state.current")
DOOR_TARGET = ("garage-door-opener", "door-state.target")
DOOR_OBSTRUCTION = ("garage-door-opener", "obstruction-detected")


def create_window_covering_service(accessory):
    """Define a window-covering characteristics as per page 219 of HAP spec."""
    service = accessory.add_service(ServicesTypes.WINDOW_COVERING)

    cur_state = service.add_char(CharacteristicsTypes.POSITION_CURRENT)
    cur_state.value = 0

    targ_state = service.add_char(CharacteristicsTypes.POSITION_TARGET)
    targ_state.value = 0

    position_state = service.add_char(CharacteristicsTypes.POSITION_STATE)
    position_state.value = 0

    position_hold = service.add_char(CharacteristicsTypes.POSITION_HOLD)
    position_hold.value = 0

    obstruction = service.add_char(CharacteristicsTypes.OBSTRUCTION_DETECTED)
    obstruction.value = False

    name = service.add_char(CharacteristicsTypes.NAME)
    name.value = "testdevice"

    return service


def create_window_covering_service_with_h_tilt(accessory):
    """Define a window-covering characteristics as per page 219 of HAP spec."""
    service = create_window_covering_service(accessory)

    tilt_current = service.add_char(CharacteristicsTypes.HORIZONTAL_TILT_CURRENT)
    tilt_current.value = 0

    tilt_target = service.add_char(CharacteristicsTypes.HORIZONTAL_TILT_TARGET)
    tilt_target.value = 0


def create_window_covering_service_with_v_tilt(accessory):
    """Define a window-covering characteristics as per page 219 of HAP spec."""
    service = create_window_covering_service(accessory)

    tilt_current = service.add_char(CharacteristicsTypes.VERTICAL_TILT_CURRENT)
    tilt_current.value = 0

    tilt_target = service.add_char(CharacteristicsTypes.VERTICAL_TILT_TARGET)
    tilt_target.value = 0


async def test_change_window_cover_state(hass, utcnow):
    """Test that we can turn a HomeKit alarm on and off again."""
    helper = await setup_test_component(hass, create_window_covering_service)

    await hass.services.async_call(
        "cover", "open_cover", {"entity_id": helper.entity_id}, blocking=True
    )
    assert helper.characteristics[POSITION_TARGET].value == 100

    await hass.services.async_call(
        "cover", "close_cover", {"entity_id": helper.entity_id}, blocking=True
    )
    assert helper.characteristics[POSITION_TARGET].value == 0


async def test_read_window_cover_state(hass, utcnow):
    """Test that we can read the state of a HomeKit alarm accessory."""
    helper = await setup_test_component(hass, create_window_covering_service)

    helper.characteristics[POSITION_STATE].value = 0
    state = await helper.poll_and_get_state()
    assert state.state == "closing"

    helper.characteristics[POSITION_STATE].value = 1
    state = await helper.poll_and_get_state()
    assert state.state == "opening"

    helper.characteristics[POSITION_STATE].value = 2
    state = await helper.poll_and_get_state()
    assert state.state == "closed"

    helper.characteristics[WINDOW_OBSTRUCTION].value = True
    state = await helper.poll_and_get_state()
    assert state.attributes["obstruction-detected"] is True


async def test_read_window_cover_tilt_horizontal(hass, utcnow):
    """Test that horizontal tilt is handled correctly."""
    helper = await setup_test_component(
        hass, create_window_covering_service_with_h_tilt
    )

    helper.characteristics[H_TILT_CURRENT].value = 75
    state = await helper.poll_and_get_state()
    assert state.attributes["current_tilt_position"] == 75


async def test_read_window_cover_tilt_vertical(hass, utcnow):
    """Test that vertical tilt is handled correctly."""
    helper = await setup_test_component(
        hass, create_window_covering_service_with_v_tilt
    )

    helper.characteristics[V_TILT_CURRENT].value = 75
    state = await helper.poll_and_get_state()
    assert state.attributes["current_tilt_position"] == 75


async def test_write_window_cover_tilt_horizontal(hass, utcnow):
    """Test that horizontal tilt is written correctly."""
    helper = await setup_test_component(
        hass, create_window_covering_service_with_h_tilt
    )

    await hass.services.async_call(
        "cover",
        "set_cover_tilt_position",
        {"entity_id": helper.entity_id, "tilt_position": 90},
        blocking=True,
    )
    assert helper.characteristics[H_TILT_TARGET].value == 90


async def test_write_window_cover_tilt_vertical(hass, utcnow):
    """Test that vertical tilt is written correctly."""
    helper = await setup_test_component(
        hass, create_window_covering_service_with_v_tilt
    )

    await hass.services.async_call(
        "cover",
        "set_cover_tilt_position",
        {"entity_id": helper.entity_id, "tilt_position": 90},
        blocking=True,
    )
    assert helper.characteristics[V_TILT_TARGET].value == 90


async def test_window_cover_stop(hass, utcnow):
    """Test that vertical tilt is written correctly."""
    helper = await setup_test_component(
        hass, create_window_covering_service_with_v_tilt
    )

    await hass.services.async_call(
        "cover", "stop_cover", {"entity_id": helper.entity_id}, blocking=True
    )
    assert helper.characteristics[POSITION_HOLD].value == 1


def create_garage_door_opener_service(accessory):
    """Define a garage-door-opener chars as per page 217 of HAP spec."""
    service = accessory.add_service(ServicesTypes.GARAGE_DOOR_OPENER)

    cur_state = service.add_char(CharacteristicsTypes.DOOR_STATE_CURRENT)
    cur_state.value = 0

    cur_state = service.add_char(CharacteristicsTypes.DOOR_STATE_TARGET)
    cur_state.value = 0

    obstruction = service.add_char(CharacteristicsTypes.OBSTRUCTION_DETECTED)
    obstruction.value = False

    name = service.add_char(CharacteristicsTypes.NAME)
    name.value = "testdevice"

    return service


async def test_change_door_state(hass, utcnow):
    """Test that we can turn open and close a HomeKit garage door."""
    helper = await setup_test_component(hass, create_garage_door_opener_service)

    await hass.services.async_call(
        "cover", "open_cover", {"entity_id": helper.entity_id}, blocking=True
    )
    assert helper.characteristics[DOOR_TARGET].value == 0

    await hass.services.async_call(
        "cover", "close_cover", {"entity_id": helper.entity_id}, blocking=True
    )
    assert helper.characteristics[DOOR_TARGET].value == 1


async def test_read_door_state(hass, utcnow):
    """Test that we can read the state of a HomeKit garage door."""
    helper = await setup_test_component(hass, create_garage_door_opener_service)

    helper.characteristics[DOOR_CURRENT].value = 0
    state = await helper.poll_and_get_state()
    assert state.state == "open"

    helper.characteristics[DOOR_CURRENT].value = 1
    state = await helper.poll_and_get_state()
    assert state.state == "closed"

    helper.characteristics[DOOR_CURRENT].value = 2
    state = await helper.poll_and_get_state()
    assert state.state == "opening"

    helper.characteristics[DOOR_CURRENT].value = 3
    state = await helper.poll_and_get_state()
    assert state.state == "closing"

    helper.characteristics[DOOR_OBSTRUCTION].value = True
    state = await helper.poll_and_get_state()
    assert state.attributes["obstruction-detected"] is True
