"""Basic checks for HomeKitLock."""
from tests.components.homekit_controller.common import (
    FakeService, setup_test_component)

MOTION_DETECTED = ('motion', 'motion-detected')


def create_sensor_motion_service():
    """Define motion characteristics as per page 225 of HAP spec."""
    service = FakeService('public.hap.service.sensor.motion')

    cur_state = service.add_characteristic('motion-detected')
    cur_state.value = 0

    return service


async def test_sensor_read_state(hass, utcnow):
    """Test that we can read the state of a HomeKit motion sensor accessory."""
    sensor = create_sensor_motion_service()
    helper = await setup_test_component(hass, [sensor])

    helper.characteristics[MOTION_DETECTED].value = False
    state = await helper.poll_and_get_state()
    assert state.state == 'off'

    helper.characteristics[MOTION_DETECTED].value = True
    state = await helper.poll_and_get_state()
    assert state.state == 'on'
