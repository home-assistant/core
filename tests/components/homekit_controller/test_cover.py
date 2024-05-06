"""Basic checks for HomeKitalarm_control_panel."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import get_next_aid, setup_test_component


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
    tilt_current.minValue = 0
    tilt_current.maxValue = 90

    tilt_target = service.add_char(CharacteristicsTypes.HORIZONTAL_TILT_TARGET)
    tilt_target.value = 0
    tilt_target.minValue = 0
    tilt_target.maxValue = 90


def create_window_covering_service_with_h_tilt_2(accessory):
    """Define a window-covering characteristics as per page 219 of HAP spec."""
    service = create_window_covering_service(accessory)

    tilt_current = service.add_char(CharacteristicsTypes.HORIZONTAL_TILT_CURRENT)
    tilt_current.value = 0
    tilt_current.minValue = -90
    tilt_current.maxValue = 0

    tilt_target = service.add_char(CharacteristicsTypes.HORIZONTAL_TILT_TARGET)
    tilt_target.value = 0
    tilt_target.minValue = -90
    tilt_target.maxValue = 0


def create_window_covering_service_with_v_tilt(accessory):
    """Define a window-covering characteristics as per page 219 of HAP spec."""
    service = create_window_covering_service(accessory)

    tilt_current = service.add_char(CharacteristicsTypes.VERTICAL_TILT_CURRENT)
    tilt_current.value = 0
    tilt_current.minValue = 0
    tilt_current.maxValue = 90

    tilt_target = service.add_char(CharacteristicsTypes.VERTICAL_TILT_TARGET)
    tilt_target.value = 0
    tilt_target.minValue = 0
    tilt_target.maxValue = 90


def create_window_covering_service_with_v_tilt_2(accessory):
    """Define a window-covering characteristics as per page 219 of HAP spec."""
    service = create_window_covering_service(accessory)

    tilt_current = service.add_char(CharacteristicsTypes.VERTICAL_TILT_CURRENT)
    tilt_current.value = 0
    tilt_current.minValue = -90
    tilt_current.maxValue = 0

    tilt_target = service.add_char(CharacteristicsTypes.VERTICAL_TILT_TARGET)
    tilt_target.value = 0
    tilt_target.minValue = -90
    tilt_target.maxValue = 0


async def test_change_window_cover_state(hass: HomeAssistant) -> None:
    """Test that we can turn a HomeKit alarm on and off again."""
    helper = await setup_test_component(hass, create_window_covering_service)

    await hass.services.async_call(
        "cover", "open_cover", {"entity_id": helper.entity_id}, blocking=True
    )
    helper.async_assert_service_values(
        ServicesTypes.WINDOW_COVERING,
        {
            CharacteristicsTypes.POSITION_TARGET: 100,
        },
    )

    await hass.services.async_call(
        "cover", "close_cover", {"entity_id": helper.entity_id}, blocking=True
    )
    helper.async_assert_service_values(
        ServicesTypes.WINDOW_COVERING,
        {
            CharacteristicsTypes.POSITION_TARGET: 0,
        },
    )


async def test_read_window_cover_state(hass: HomeAssistant) -> None:
    """Test that we can read the state of a HomeKit alarm accessory."""
    helper = await setup_test_component(hass, create_window_covering_service)

    await helper.async_update(
        ServicesTypes.WINDOW_COVERING,
        {CharacteristicsTypes.POSITION_STATE: 0},
    )
    state = await helper.poll_and_get_state()
    assert state.state == "closing"

    await helper.async_update(
        ServicesTypes.WINDOW_COVERING,
        {CharacteristicsTypes.POSITION_STATE: 1},
    )
    state = await helper.poll_and_get_state()
    assert state.state == "opening"

    await helper.async_update(
        ServicesTypes.WINDOW_COVERING,
        {CharacteristicsTypes.POSITION_STATE: 2},
    )
    state = await helper.poll_and_get_state()
    assert state.state == "closed"

    await helper.async_update(
        ServicesTypes.WINDOW_COVERING,
        {CharacteristicsTypes.OBSTRUCTION_DETECTED: True},
    )
    state = await helper.poll_and_get_state()
    assert state.attributes["obstruction-detected"] is True


async def test_read_window_cover_tilt_horizontal(hass: HomeAssistant) -> None:
    """Test that horizontal tilt is handled correctly."""
    helper = await setup_test_component(
        hass, create_window_covering_service_with_h_tilt
    )

    await helper.async_update(
        ServicesTypes.WINDOW_COVERING,
        {CharacteristicsTypes.HORIZONTAL_TILT_CURRENT: 75},
    )
    state = await helper.poll_and_get_state()
    # Expect converted value from arcdegree scale to percentage scale.
    assert state.attributes["current_tilt_position"] == 83


async def test_read_window_cover_tilt_horizontal_2(hass: HomeAssistant) -> None:
    """Test that horizontal tilt is handled correctly."""
    helper = await setup_test_component(
        hass, create_window_covering_service_with_h_tilt_2
    )

    await helper.async_update(
        ServicesTypes.WINDOW_COVERING,
        {CharacteristicsTypes.HORIZONTAL_TILT_CURRENT: -75},
    )
    state = await helper.poll_and_get_state()
    # Expect converted value from arcdegree scale to percentage scale.
    assert state.attributes["current_tilt_position"] == 83


async def test_read_window_cover_tilt_vertical(hass: HomeAssistant) -> None:
    """Test that vertical tilt is handled correctly."""
    helper = await setup_test_component(
        hass, create_window_covering_service_with_v_tilt
    )

    await helper.async_update(
        ServicesTypes.WINDOW_COVERING,
        {CharacteristicsTypes.VERTICAL_TILT_CURRENT: 75},
    )
    state = await helper.poll_and_get_state()
    # Expect converted value from arcdegree scale to percentage scale.
    assert state.attributes["current_tilt_position"] == 83


async def test_read_window_cover_tilt_vertical_2(hass: HomeAssistant) -> None:
    """Test that vertical tilt is handled correctly."""
    helper = await setup_test_component(
        hass, create_window_covering_service_with_v_tilt_2
    )

    await helper.async_update(
        ServicesTypes.WINDOW_COVERING,
        {CharacteristicsTypes.VERTICAL_TILT_CURRENT: -75},
    )
    state = await helper.poll_and_get_state()
    # Expect converted value from arcdegree scale to percentage scale.
    assert state.attributes["current_tilt_position"] == 83


async def test_write_window_cover_tilt_horizontal(hass: HomeAssistant) -> None:
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
    # Expect converted value from percentage scale to arcdegree scale.
    helper.async_assert_service_values(
        ServicesTypes.WINDOW_COVERING,
        {
            CharacteristicsTypes.HORIZONTAL_TILT_TARGET: 81,
        },
    )


async def test_write_window_cover_tilt_horizontal_2(hass: HomeAssistant) -> None:
    """Test that horizontal tilt is written correctly."""
    helper = await setup_test_component(
        hass, create_window_covering_service_with_h_tilt_2
    )

    await hass.services.async_call(
        "cover",
        "set_cover_tilt_position",
        {"entity_id": helper.entity_id, "tilt_position": 90},
        blocking=True,
    )
    # Expect converted value from percentage scale to arcdegree scale.
    helper.async_assert_service_values(
        ServicesTypes.WINDOW_COVERING,
        {
            CharacteristicsTypes.HORIZONTAL_TILT_TARGET: -81,
        },
    )


async def test_write_window_cover_tilt_vertical(hass: HomeAssistant) -> None:
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
    # Expect converted value from percentage scale to arcdegree scale.
    helper.async_assert_service_values(
        ServicesTypes.WINDOW_COVERING,
        {
            CharacteristicsTypes.VERTICAL_TILT_TARGET: 81,
        },
    )


async def test_write_window_cover_tilt_vertical_2(hass: HomeAssistant) -> None:
    """Test that vertical tilt is written correctly."""
    helper = await setup_test_component(
        hass, create_window_covering_service_with_v_tilt_2
    )

    await hass.services.async_call(
        "cover",
        "set_cover_tilt_position",
        {"entity_id": helper.entity_id, "tilt_position": 90},
        blocking=True,
    )
    # Expect converted value from percentage scale to arcdegree scale.
    helper.async_assert_service_values(
        ServicesTypes.WINDOW_COVERING,
        {
            CharacteristicsTypes.VERTICAL_TILT_TARGET: -81,
        },
    )


async def test_window_cover_stop(hass: HomeAssistant) -> None:
    """Test that vertical tilt is written correctly."""
    helper = await setup_test_component(
        hass, create_window_covering_service_with_v_tilt
    )

    await hass.services.async_call(
        "cover", "stop_cover", {"entity_id": helper.entity_id}, blocking=True
    )
    helper.async_assert_service_values(
        ServicesTypes.WINDOW_COVERING,
        {
            CharacteristicsTypes.POSITION_HOLD: True,
        },
    )


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


async def test_change_door_state(hass: HomeAssistant) -> None:
    """Test that we can turn open and close a HomeKit garage door."""
    helper = await setup_test_component(hass, create_garage_door_opener_service)

    await hass.services.async_call(
        "cover", "open_cover", {"entity_id": helper.entity_id}, blocking=True
    )
    helper.async_assert_service_values(
        ServicesTypes.GARAGE_DOOR_OPENER,
        {
            CharacteristicsTypes.DOOR_STATE_TARGET: 0,
        },
    )

    await hass.services.async_call(
        "cover", "close_cover", {"entity_id": helper.entity_id}, blocking=True
    )
    helper.async_assert_service_values(
        ServicesTypes.GARAGE_DOOR_OPENER,
        {
            CharacteristicsTypes.DOOR_STATE_TARGET: 1,
        },
    )


async def test_read_door_state(hass: HomeAssistant) -> None:
    """Test that we can read the state of a HomeKit garage door."""
    helper = await setup_test_component(hass, create_garage_door_opener_service)

    await helper.async_update(
        ServicesTypes.GARAGE_DOOR_OPENER,
        {CharacteristicsTypes.DOOR_STATE_CURRENT: 0},
    )
    state = await helper.poll_and_get_state()
    assert state.state == "open"

    await helper.async_update(
        ServicesTypes.GARAGE_DOOR_OPENER,
        {CharacteristicsTypes.DOOR_STATE_CURRENT: 1},
    )
    state = await helper.poll_and_get_state()
    assert state.state == "closed"

    await helper.async_update(
        ServicesTypes.GARAGE_DOOR_OPENER,
        {CharacteristicsTypes.DOOR_STATE_CURRENT: 2},
    )
    state = await helper.poll_and_get_state()
    assert state.state == "opening"

    await helper.async_update(
        ServicesTypes.GARAGE_DOOR_OPENER,
        {CharacteristicsTypes.DOOR_STATE_CURRENT: 3},
    )
    state = await helper.poll_and_get_state()
    assert state.state == "closing"

    await helper.async_update(
        ServicesTypes.GARAGE_DOOR_OPENER,
        {CharacteristicsTypes.OBSTRUCTION_DETECTED: True},
    )
    state = await helper.poll_and_get_state()
    assert state.attributes["obstruction-detected"] is True


async def test_migrate_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a we can migrate a cover unique id."""
    aid = get_next_aid()
    cover_entry = entity_registry.async_get_or_create(
        "cover",
        "homekit_controller",
        f"homekit-00:00:00:00:00:00-{aid}-8",
    )
    await setup_test_component(hass, create_garage_door_opener_service)

    assert (
        entity_registry.async_get(cover_entry.entity_id).unique_id
        == f"00:00:00:00:00:00_{aid}_8"
    )
