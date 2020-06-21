"""Basic checks for HomeKit air quality sensor."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from tests.components.homekit_controller.common import setup_test_component


def create_air_quality_sensor_service(accessory):
    """Define temperature characteristics."""
    service = accessory.add_service(ServicesTypes.AIR_QUALITY_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.AIR_QUALITY)
    cur_state.value = 5

    cur_state = service.add_char(CharacteristicsTypes.DENSITY_OZONE)
    cur_state.value = 1111

    cur_state = service.add_char(CharacteristicsTypes.DENSITY_NO2)
    cur_state.value = 2222

    cur_state = service.add_char(CharacteristicsTypes.DENSITY_SO2)
    cur_state.value = 3333

    cur_state = service.add_char(CharacteristicsTypes.DENSITY_PM25)
    cur_state.value = 4444

    cur_state = service.add_char(CharacteristicsTypes.DENSITY_PM10)
    cur_state.value = 5555

    cur_state = service.add_char(CharacteristicsTypes.DENSITY_VOC)
    cur_state.value = 6666


async def test_air_quality_sensor_read_state(hass, utcnow):
    """Test reading the state of a HomeKit temperature sensor accessory."""
    helper = await setup_test_component(hass, create_air_quality_sensor_service)

    state = await helper.poll_and_get_state()
    assert state.state == "4444"

    assert state.attributes["air_quality_text"] == "poor"
    assert state.attributes["ozone"] == 1111
    assert state.attributes["nitrogen_dioxide"] == 2222
    assert state.attributes["sulphur_dioxide"] == 3333
    assert state.attributes["particulate_matter_2_5"] == 4444
    assert state.attributes["particulate_matter_10"] == 5555
    assert state.attributes["volatile_organic_compounds"] == 6666
