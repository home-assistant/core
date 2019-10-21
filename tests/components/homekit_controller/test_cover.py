"""Basic checks for HomeKitalarm_control_panel."""
from tests.components.homekit_controller.common import FakeService, setup_test_component

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


def create_window_covering_service():
    """Define a window-covering characteristics as per page 219 of HAP spec."""
    service = FakeService("public.hap.service.window-covering")

    cur_state = service.add_characteristic("position.current")
    cur_state.value = 0

    targ_state = service.add_characteristic("position.target")
    targ_state.value = 0

    position_state = service.add_characteristic("position.state")
    position_state.value = 0

    position_hold = service.add_characteristic("position.hold")
    position_hold.value = 0

    obstruction = service.add_characteristic("obstruction-detected")
    obstruction.value = False

    name = service.add_characteristic("name")
    name.value = "testdevice"

    return service


def create_window_covering_service_with_h_tilt():
    """Define a window-covering characteristics as per page 219 of HAP spec."""
    service = create_window_covering_service()

    tilt_current = service.add_characteristic("horizontal-tilt.current")
    tilt_current.value = 0

    tilt_target = service.add_characteristic("horizontal-tilt.target")
    tilt_target.value = 0

    return service


def create_window_covering_service_with_v_tilt():
    """Define a window-covering characteristics as per page 219 of HAP spec."""
    service = create_window_covering_service()

    tilt_current = service.add_characteristic("vertical-tilt.current")
    tilt_current.value = 0

    tilt_target = service.add_characteristic("vertical-tilt.target")
    tilt_target.value = 0

    return service


async def test_change_window_cover_state(hass, utcnow):
    """Test that we can turn a HomeKit alarm on and off again."""
    window_cover = create_window_covering_service()
    helper = await setup_test_component(hass, [window_cover])

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
    window_cover = create_window_covering_service()
    helper = await setup_test_component(hass, [window_cover])

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
    window_cover = create_window_covering_service_with_h_tilt()
    helper = await setup_test_component(hass, [window_cover])

    helper.characteristics[H_TILT_CURRENT].value = 75
    state = await helper.poll_and_get_state()
    assert state.attributes["current_tilt_position"] == 75


async def test_read_window_cover_tilt_vertical(hass, utcnow):
    """Test that vertical tilt is handled correctly."""
    window_cover = create_window_covering_service_with_v_tilt()
    helper = await setup_test_component(hass, [window_cover])

    helper.characteristics[V_TILT_CURRENT].value = 75
    state = await helper.poll_and_get_state()
    assert state.attributes["current_tilt_position"] == 75


async def test_write_window_cover_tilt_horizontal(hass, utcnow):
    """Test that horizontal tilt is written correctly."""
    window_cover = create_window_covering_service_with_h_tilt()
    helper = await setup_test_component(hass, [window_cover])

    await hass.services.async_call(
        "cover",
        "set_cover_tilt_position",
        {"entity_id": helper.entity_id, "tilt_position": 90},
        blocking=True,
    )
    assert helper.characteristics[H_TILT_TARGET].value == 90


async def test_write_window_cover_tilt_vertical(hass, utcnow):
    """Test that vertical tilt is written correctly."""
    window_cover = create_window_covering_service_with_v_tilt()
    helper = await setup_test_component(hass, [window_cover])

    await hass.services.async_call(
        "cover",
        "set_cover_tilt_position",
        {"entity_id": helper.entity_id, "tilt_position": 90},
        blocking=True,
    )
    assert helper.characteristics[V_TILT_TARGET].value == 90


async def test_window_cover_stop(hass, utcnow):
    """Test that vertical tilt is written correctly."""
    window_cover = create_window_covering_service_with_v_tilt()
    helper = await setup_test_component(hass, [window_cover])

    await hass.services.async_call(
        "cover", "stop_cover", {"entity_id": helper.entity_id}, blocking=True
    )
    assert helper.characteristics[POSITION_HOLD].value == 1


def create_garage_door_opener_service():
    """Define a garage-door-opener chars as per page 217 of HAP spec."""
    service = FakeService("public.hap.service.garage-door-opener")

    cur_state = service.add_characteristic("door-state.current")
    cur_state.value = 0

    targ_state = service.add_characteristic("door-state.target")
    targ_state.value = 0

    obstruction = service.add_characteristic("obstruction-detected")
    obstruction.value = False

    name = service.add_characteristic("name")
    name.value = "testdevice"

    return service


async def test_change_door_state(hass, utcnow):
    """Test that we can turn open and close a HomeKit garage door."""
    door = create_garage_door_opener_service()
    helper = await setup_test_component(hass, [door])

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
    door = create_garage_door_opener_service()
    helper = await setup_test_component(hass, [door])

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
