"""Basic checks for HomeKit motion sensors and contact sensors."""
from tests.components.homekit_controller.common import FakeService, setup_test_component

MOTION_DETECTED = ("motion", "motion-detected")
CONTACT_STATE = ("contact", "contact-state")


def create_motion_sensor_service():
    """Define motion characteristics as per page 225 of HAP spec."""
    service = FakeService("public.hap.service.sensor.motion")

    cur_state = service.add_characteristic("motion-detected")
    cur_state.value = 0

    return service


async def test_motion_sensor_read_state(hass, utcnow):
    """Test that we can read the state of a HomeKit motion sensor accessory."""
    sensor = create_motion_sensor_service()
    helper = await setup_test_component(hass, [sensor])

    helper.characteristics[MOTION_DETECTED].value = False
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    helper.characteristics[MOTION_DETECTED].value = True
    state = await helper.poll_and_get_state()
    assert state.state == "on"


def create_contact_sensor_service():
    """Define contact characteristics."""
    service = FakeService("public.hap.service.sensor.contact")

    cur_state = service.add_characteristic("contact-state")
    cur_state.value = 0

    return service


async def test_contact_sensor_read_state(hass, utcnow):
    """Test that we can read the state of a HomeKit contact accessory."""
    sensor = create_contact_sensor_service()
    helper = await setup_test_component(hass, [sensor])

    helper.characteristics[CONTACT_STATE].value = 0
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    helper.characteristics[CONTACT_STATE].value = 1
    state = await helper.poll_and_get_state()
    assert state.state == "on"
