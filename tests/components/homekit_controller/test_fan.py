"""Basic checks for HomeKit motion sensors and contact sensors."""
from tests.components.homekit_controller.common import FakeService, setup_test_component

V1_ON = ("fan", "on")
V1_ROTATION_DIRECTION = ("fan", "rotation.direction")
V1_ROTATION_SPEED = ("fan", "rotation.speed")

V2_ACTIVE = ("fanv2", "active")
V2_ROTATION_DIRECTION = ("fanv2", "rotation.direction")
V2_ROTATION_SPEED = ("fanv2", "rotation.speed")
V2_SWING_MODE = ("fanv2", "swing-mode")


def create_fan_service():
    """
    Define fan v1 characteristics as per HAP spec.

    This service is no longer documented in R2 of the public HAP spec but existing
    devices out there use it (like the SIMPLEconnect fan)
    """
    service = FakeService("public.hap.service.fan")

    cur_state = service.add_characteristic("on")
    cur_state.value = 0

    cur_state = service.add_characteristic("rotation.direction")
    cur_state.value = 0

    cur_state = service.add_characteristic("rotation.speed")
    cur_state.value = 0

    return service


def create_fanv2_service():
    """Define fan v2 characteristics as per HAP spec."""
    service = FakeService("public.hap.service.fanv2")

    cur_state = service.add_characteristic("active")
    cur_state.value = 0

    cur_state = service.add_characteristic("rotation.direction")
    cur_state.value = 0

    cur_state = service.add_characteristic("rotation.speed")
    cur_state.value = 0

    cur_state = service.add_characteristic("swing-mode")
    cur_state.value = 0

    return service


async def test_fan_read_state(hass, utcnow):
    """Test that we can read the state of a HomeKit fan accessory."""
    sensor = create_fan_service()
    helper = await setup_test_component(hass, [sensor])

    helper.characteristics[V1_ON].value = False
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    helper.characteristics[V1_ON].value = True
    state = await helper.poll_and_get_state()
    assert state.state == "on"


async def test_turn_on(hass, utcnow):
    """Test that we can turn a fan on."""
    fan = create_fan_service()
    helper = await setup_test_component(hass, [fan])

    await hass.services.async_call(
        "fan",
        "turn_on",
        {"entity_id": "fan.testdevice", "speed": "high"},
        blocking=True,
    )
    assert helper.characteristics[V1_ON].value == 1
    assert helper.characteristics[V1_ROTATION_SPEED].value == 100

    await hass.services.async_call(
        "fan",
        "turn_on",
        {"entity_id": "fan.testdevice", "speed": "medium"},
        blocking=True,
    )
    assert helper.characteristics[V1_ON].value == 1
    assert helper.characteristics[V1_ROTATION_SPEED].value == 50

    await hass.services.async_call(
        "fan",
        "turn_on",
        {"entity_id": "fan.testdevice", "speed": "low"},
        blocking=True,
    )
    assert helper.characteristics[V1_ON].value == 1
    assert helper.characteristics[V1_ROTATION_SPEED].value == 25


async def test_turn_off(hass, utcnow):
    """Test that we can turn a fan off."""
    fan = create_fan_service()
    helper = await setup_test_component(hass, [fan])

    helper.characteristics[V1_ON].value = 1

    await hass.services.async_call(
        "fan", "turn_off", {"entity_id": "fan.testdevice"}, blocking=True,
    )
    assert helper.characteristics[V1_ON].value == 0


async def test_set_speed(hass, utcnow):
    """Test that we set fan speed."""
    fan = create_fan_service()
    helper = await setup_test_component(hass, [fan])

    helper.characteristics[V1_ON].value = 1

    await hass.services.async_call(
        "fan",
        "set_speed",
        {"entity_id": "fan.testdevice", "speed": "high"},
        blocking=True,
    )
    assert helper.characteristics[V1_ROTATION_SPEED].value == 100

    await hass.services.async_call(
        "fan",
        "set_speed",
        {"entity_id": "fan.testdevice", "speed": "medium"},
        blocking=True,
    )
    assert helper.characteristics[V1_ROTATION_SPEED].value == 50

    await hass.services.async_call(
        "fan",
        "set_speed",
        {"entity_id": "fan.testdevice", "speed": "low"},
        blocking=True,
    )
    assert helper.characteristics[V1_ROTATION_SPEED].value == 25

    await hass.services.async_call(
        "fan",
        "set_speed",
        {"entity_id": "fan.testdevice", "speed": "off"},
        blocking=True,
    )
    assert helper.characteristics[V1_ON].value == 0


async def test_speed_read(hass, utcnow):
    """Test that we can read a fans oscillation."""
    fan = create_fan_service()
    helper = await setup_test_component(hass, [fan])

    helper.characteristics[V1_ON].value = 1
    helper.characteristics[V1_ROTATION_SPEED].value = 100
    state = await helper.poll_and_get_state()
    assert state.attributes["speed"] == "high"

    helper.characteristics[V1_ROTATION_SPEED].value = 50
    state = await helper.poll_and_get_state()
    assert state.attributes["speed"] == "medium"

    helper.characteristics[V1_ROTATION_SPEED].value = 25
    state = await helper.poll_and_get_state()
    assert state.attributes["speed"] == "low"

    helper.characteristics[V1_ON].value = 0
    helper.characteristics[V1_ROTATION_SPEED].value = 0
    state = await helper.poll_and_get_state()
    assert state.attributes["speed"] == "off"


async def test_set_direction(hass, utcnow):
    """Test that we can set fan spin direction."""
    fan = create_fan_service()
    helper = await setup_test_component(hass, [fan])

    await hass.services.async_call(
        "fan",
        "set_direction",
        {"entity_id": "fan.testdevice", "direction": "reverse"},
        blocking=True,
    )
    assert helper.characteristics[V1_ROTATION_DIRECTION].value == 1

    await hass.services.async_call(
        "fan",
        "set_direction",
        {"entity_id": "fan.testdevice", "direction": "forward"},
        blocking=True,
    )
    assert helper.characteristics[V1_ROTATION_DIRECTION].value == 0


async def test_direction_read(hass, utcnow):
    """Test that we can read a fans oscillation."""
    fan = create_fan_service()
    helper = await setup_test_component(hass, [fan])

    helper.characteristics[V1_ROTATION_DIRECTION].value = 0
    state = await helper.poll_and_get_state()
    assert state.attributes["direction"] == "forward"

    helper.characteristics[V1_ROTATION_DIRECTION].value = 1
    state = await helper.poll_and_get_state()
    assert state.attributes["direction"] == "reverse"


async def test_fanv2_read_state(hass, utcnow):
    """Test that we can read the state of a HomeKit fan accessory."""
    sensor = create_fanv2_service()
    helper = await setup_test_component(hass, [sensor])

    helper.characteristics[V2_ACTIVE].value = False
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    helper.characteristics[V2_ACTIVE].value = True
    state = await helper.poll_and_get_state()
    assert state.state == "on"


async def test_v2_turn_on(hass, utcnow):
    """Test that we can turn a fan on."""
    fan = create_fanv2_service()
    helper = await setup_test_component(hass, [fan])

    await hass.services.async_call(
        "fan",
        "turn_on",
        {"entity_id": "fan.testdevice", "speed": "high"},
        blocking=True,
    )
    assert helper.characteristics[V2_ACTIVE].value == 1
    assert helper.characteristics[V2_ROTATION_SPEED].value == 100

    await hass.services.async_call(
        "fan",
        "turn_on",
        {"entity_id": "fan.testdevice", "speed": "medium"},
        blocking=True,
    )
    assert helper.characteristics[V2_ACTIVE].value == 1
    assert helper.characteristics[V2_ROTATION_SPEED].value == 50

    await hass.services.async_call(
        "fan",
        "turn_on",
        {"entity_id": "fan.testdevice", "speed": "low"},
        blocking=True,
    )
    assert helper.characteristics[V2_ACTIVE].value == 1
    assert helper.characteristics[V2_ROTATION_SPEED].value == 25


async def test_v2_turn_off(hass, utcnow):
    """Test that we can turn a fan off."""
    fan = create_fanv2_service()
    helper = await setup_test_component(hass, [fan])

    helper.characteristics[V2_ACTIVE].value = 1

    await hass.services.async_call(
        "fan", "turn_off", {"entity_id": "fan.testdevice"}, blocking=True,
    )
    assert helper.characteristics[V2_ACTIVE].value == 0


async def test_v2_set_speed(hass, utcnow):
    """Test that we set fan speed."""
    fan = create_fanv2_service()
    helper = await setup_test_component(hass, [fan])

    helper.characteristics[V2_ACTIVE].value = 1

    await hass.services.async_call(
        "fan",
        "set_speed",
        {"entity_id": "fan.testdevice", "speed": "high"},
        blocking=True,
    )
    assert helper.characteristics[V2_ROTATION_SPEED].value == 100

    await hass.services.async_call(
        "fan",
        "set_speed",
        {"entity_id": "fan.testdevice", "speed": "medium"},
        blocking=True,
    )
    assert helper.characteristics[V2_ROTATION_SPEED].value == 50

    await hass.services.async_call(
        "fan",
        "set_speed",
        {"entity_id": "fan.testdevice", "speed": "low"},
        blocking=True,
    )
    assert helper.characteristics[V2_ROTATION_SPEED].value == 25

    await hass.services.async_call(
        "fan",
        "set_speed",
        {"entity_id": "fan.testdevice", "speed": "off"},
        blocking=True,
    )
    assert helper.characteristics[V2_ACTIVE].value == 0


async def test_v2_speed_read(hass, utcnow):
    """Test that we can read a fans oscillation."""
    fan = create_fanv2_service()
    helper = await setup_test_component(hass, [fan])

    helper.characteristics[V2_ACTIVE].value = 1
    helper.characteristics[V2_ROTATION_SPEED].value = 100
    state = await helper.poll_and_get_state()
    assert state.attributes["speed"] == "high"

    helper.characteristics[V2_ROTATION_SPEED].value = 50
    state = await helper.poll_and_get_state()
    assert state.attributes["speed"] == "medium"

    helper.characteristics[V2_ROTATION_SPEED].value = 25
    state = await helper.poll_and_get_state()
    assert state.attributes["speed"] == "low"

    helper.characteristics[V2_ACTIVE].value = 0
    helper.characteristics[V2_ROTATION_SPEED].value = 0
    state = await helper.poll_and_get_state()
    assert state.attributes["speed"] == "off"


async def test_v2_set_direction(hass, utcnow):
    """Test that we can set fan spin direction."""
    fan = create_fanv2_service()
    helper = await setup_test_component(hass, [fan])

    await hass.services.async_call(
        "fan",
        "set_direction",
        {"entity_id": "fan.testdevice", "direction": "reverse"},
        blocking=True,
    )
    assert helper.characteristics[V2_ROTATION_DIRECTION].value == 1

    await hass.services.async_call(
        "fan",
        "set_direction",
        {"entity_id": "fan.testdevice", "direction": "forward"},
        blocking=True,
    )
    assert helper.characteristics[V2_ROTATION_DIRECTION].value == 0


async def test_v2_direction_read(hass, utcnow):
    """Test that we can read a fans oscillation."""
    fan = create_fanv2_service()
    helper = await setup_test_component(hass, [fan])

    helper.characteristics[V2_ROTATION_DIRECTION].value = 0
    state = await helper.poll_and_get_state()
    assert state.attributes["direction"] == "forward"

    helper.characteristics[V2_ROTATION_DIRECTION].value = 1
    state = await helper.poll_and_get_state()
    assert state.attributes["direction"] == "reverse"


async def test_v2_oscillate(hass, utcnow):
    """Test that we can control a fans oscillation."""
    fan = create_fanv2_service()
    helper = await setup_test_component(hass, [fan])

    await hass.services.async_call(
        "fan",
        "oscillate",
        {"entity_id": "fan.testdevice", "oscillating": True},
        blocking=True,
    )
    assert helper.characteristics[V2_SWING_MODE].value == 1

    await hass.services.async_call(
        "fan",
        "oscillate",
        {"entity_id": "fan.testdevice", "oscillating": False},
        blocking=True,
    )
    assert helper.characteristics[V2_SWING_MODE].value == 0


async def test_v2_oscillate_read(hass, utcnow):
    """Test that we can read a fans oscillation."""
    fan = create_fanv2_service()
    helper = await setup_test_component(hass, [fan])

    helper.characteristics[V2_SWING_MODE].value = 0
    state = await helper.poll_and_get_state()
    assert state.attributes["oscillating"] is False

    helper.characteristics[V2_SWING_MODE].value = 1
    state = await helper.poll_and_get_state()
    assert state.attributes["oscillating"] is True
