"""Basic checks for HomeKit air quality sensor."""
from tests.components.homekit_controller.common import FakeService, setup_test_component


def create_air_quality_sensor_service():
    """Define temperature characteristics."""
    service = FakeService("public.hap.service.sensor.air-quality")

    cur_state = service.add_characteristic("air-quality")
    cur_state.value = 5

    cur_state = service.add_characteristic("density.ozone")
    cur_state.value = 1111

    cur_state = service.add_characteristic("density.no2")
    cur_state.value = 2222

    cur_state = service.add_characteristic("density.so2")
    cur_state.value = 3333

    cur_state = service.add_characteristic("density.pm25")
    cur_state.value = 4444

    cur_state = service.add_characteristic("density.pm10")
    cur_state.value = 5555

    cur_state = service.add_characteristic("density.voc")
    cur_state.value = 6666

    return service


async def test_air_quality_sensor_read_state(hass, utcnow):
    """Test reading the state of a HomeKit temperature sensor accessory."""
    sensor = create_air_quality_sensor_service()
    helper = await setup_test_component(hass, [sensor])

    state = await helper.poll_and_get_state()
    assert state.state == "4444"

    assert state.attributes["air_quality_text"] == "poor"
    assert state.attributes["ozone"] == 1111
    assert state.attributes["nitrogen_dioxide"] == 2222
    assert state.attributes["sulphur_dioxide"] == 3333
    assert state.attributes["particulate_matter_2_5"] == 4444
    assert state.attributes["particulate_matter_10"] == 5555
    assert state.attributes["volatile_organic_compounds"] == 6666
