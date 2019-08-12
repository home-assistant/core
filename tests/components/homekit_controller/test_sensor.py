"""Basic checks for HomeKit sensor."""
from tests.components.homekit_controller.common import (
    FakeService, setup_test_component)

TEMPERATURE = ('temperature', 'temperature.current')
HUMIDITY = ('humidity', 'relative-humidity.current')
LIGHT_LEVEL = ('light', 'light-level.current')


def create_temperature_sensor_service():
    """Define temperature characteristics."""
    service = FakeService('public.hap.service.sensor.temperature')

    cur_state = service.add_characteristic('temperature.current')
    cur_state.value = 0

    return service


def create_humidity_sensor_service():
    """Define humidity characteristics."""
    service = FakeService('public.hap.service.sensor.humidity')

    cur_state = service.add_characteristic('relative-humidity.current')
    cur_state.value = 0

    return service


def create_light_level_sensor_service():
    """Define light level characteristics."""
    service = FakeService('public.hap.service.sensor.light')

    cur_state = service.add_characteristic('light-level.current')
    cur_state.value = 0

    return service


async def test_temperature_sensor_read_state(hass, utcnow):
    """Test reading the state of a HomeKit temperature sensor accessory."""
    sensor = create_temperature_sensor_service()
    helper = await setup_test_component(hass, [sensor], suffix="temperature")

    helper.characteristics[TEMPERATURE].value = 10
    state = await helper.poll_and_get_state()
    assert state.state == '10'

    helper.characteristics[TEMPERATURE].value = 20
    state = await helper.poll_and_get_state()
    assert state.state == '20'


async def test_humidity_sensor_read_state(hass, utcnow):
    """Test reading the state of a HomeKit humidity sensor accessory."""
    sensor = create_humidity_sensor_service()
    helper = await setup_test_component(hass, [sensor], suffix="humidity")

    helper.characteristics[HUMIDITY].value = 10
    state = await helper.poll_and_get_state()
    assert state.state == '10'

    helper.characteristics[HUMIDITY].value = 20
    state = await helper.poll_and_get_state()
    assert state.state == '20'


async def test_light_level_sensor_read_state(hass, utcnow):
    """Test reading the state of a HomeKit temperature sensor accessory."""
    sensor = create_light_level_sensor_service()
    helper = await setup_test_component(hass, [sensor], suffix="light_level")

    helper.characteristics[LIGHT_LEVEL].value = 10
    state = await helper.poll_and_get_state()
    assert state.state == '10'

    helper.characteristics[LIGHT_LEVEL].value = 20
    state = await helper.poll_and_get_state()
    assert state.state == '20'
