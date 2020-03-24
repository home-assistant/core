"""Basic checks for HomeKit motion sensors and contact sensors."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OCCUPANCY,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_SMOKE,
)

from tests.components.homekit_controller.common import setup_test_component

MOTION_DETECTED = ("motion", "motion-detected")
CONTACT_STATE = ("contact", "contact-state")
SMOKE_DETECTED = ("smoke", "smoke-detected")
OCCUPANCY_DETECTED = ("occupancy", "occupancy-detected")
LEAK_DETECTED = ("leak", "leak-detected")


def create_motion_sensor_service(accessory):
    """Define motion characteristics as per page 225 of HAP spec."""
    service = accessory.add_service(ServicesTypes.MOTION_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.MOTION_DETECTED)
    cur_state.value = 0


async def test_motion_sensor_read_state(hass, utcnow):
    """Test that we can read the state of a HomeKit motion sensor accessory."""
    helper = await setup_test_component(hass, create_motion_sensor_service)

    helper.characteristics[MOTION_DETECTED].value = False
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    helper.characteristics[MOTION_DETECTED].value = True
    state = await helper.poll_and_get_state()
    assert state.state == "on"

    assert state.attributes["device_class"] == DEVICE_CLASS_MOTION


def create_contact_sensor_service(accessory):
    """Define contact characteristics."""
    service = accessory.add_service(ServicesTypes.CONTACT_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.CONTACT_STATE)
    cur_state.value = 0


async def test_contact_sensor_read_state(hass, utcnow):
    """Test that we can read the state of a HomeKit contact accessory."""
    helper = await setup_test_component(hass, create_contact_sensor_service)

    helper.characteristics[CONTACT_STATE].value = 0
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    helper.characteristics[CONTACT_STATE].value = 1
    state = await helper.poll_and_get_state()
    assert state.state == "on"

    assert state.attributes["device_class"] == DEVICE_CLASS_OPENING


def create_smoke_sensor_service(accessory):
    """Define smoke sensor characteristics."""
    service = accessory.add_service(ServicesTypes.SMOKE_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.SMOKE_DETECTED)
    cur_state.value = 0


async def test_smoke_sensor_read_state(hass, utcnow):
    """Test that we can read the state of a HomeKit contact accessory."""
    helper = await setup_test_component(hass, create_smoke_sensor_service)

    helper.characteristics[SMOKE_DETECTED].value = 0
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    helper.characteristics[SMOKE_DETECTED].value = 1
    state = await helper.poll_and_get_state()
    assert state.state == "on"

    assert state.attributes["device_class"] == DEVICE_CLASS_SMOKE


def create_occupancy_sensor_service(accessory):
    """Define occupancy characteristics."""
    service = accessory.add_service(ServicesTypes.OCCUPANCY_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.OCCUPANCY_DETECTED)
    cur_state.value = 0


async def test_occupancy_sensor_read_state(hass, utcnow):
    """Test that we can read the state of a HomeKit occupancy sensor accessory."""
    helper = await setup_test_component(hass, create_occupancy_sensor_service)

    helper.characteristics[OCCUPANCY_DETECTED].value = False
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    helper.characteristics[OCCUPANCY_DETECTED].value = True
    state = await helper.poll_and_get_state()
    assert state.state == "on"

    assert state.attributes["device_class"] == DEVICE_CLASS_OCCUPANCY


def create_leak_sensor_service(accessory):
    """Define leak characteristics."""
    service = accessory.add_service(ServicesTypes.LEAK_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.LEAK_DETECTED)
    cur_state.value = 0


async def test_leak_sensor_read_state(hass, utcnow):
    """Test that we can read the state of a HomeKit leak sensor accessory."""
    helper = await setup_test_component(hass, create_leak_sensor_service)

    helper.characteristics[LEAK_DETECTED].value = 0
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    helper.characteristics[LEAK_DETECTED].value = 1
    state = await helper.poll_and_get_state()
    assert state.state == "on"

    assert state.attributes["device_class"] == DEVICE_CLASS_MOISTURE
