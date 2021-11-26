"""Basic checks for HomeKit air quality sensor."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
from homeassistant.helpers import entity_registry as er

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

    entity_registry = er.async_get(hass)
    entity_registry.async_update_entity(
        entity_id="air_quality.testdevice", disabled_by=None
    )
    await hass.async_block_till_done()

    state = await helper.poll_and_get_state()
    assert state.state == "4444"

    assert state.attributes["air_quality_text"] == "poor"
    assert state.attributes["ozone"] == 1111
    assert state.attributes["nitrogen_dioxide"] == 2222
    assert state.attributes["sulphur_dioxide"] == 3333
    assert state.attributes["particulate_matter_2_5"] == 4444
    assert state.attributes["particulate_matter_10"] == 5555
    assert state.attributes["volatile_organic_compounds"] == 6666


async def test_air_quality_sensor_read_state_even_if_air_quality_off(hass, utcnow):
    """The air quality entity is disabled by default, the replacement sensors should always be available."""
    await setup_test_component(hass, create_air_quality_sensor_service)

    entity_registry = er.async_get(hass)

    sensors = [
        {"entity_id": "sensor.testdevice_air_quality"},
        {
            "entity_id": "sensor.testdevice_pm10_density",
            "units": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        },
        {
            "entity_id": "sensor.testdevice_pm2_5_density",
            "units": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        },
        {
            "entity_id": "sensor.testdevice_pm10_density",
            "units": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        },
        {
            "entity_id": "sensor.testdevice_ozone_density",
            "units": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        },
        {
            "entity_id": "sensor.testdevice_sulphur_dioxide_density",
            "units": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        },
        {
            "entity_id": "sensor.testdevice_nitrogen_dioxide_density",
            "units": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        },
        {
            "entity_id": "sensor.testdevice_volatile_organic_compound_density",
            "units": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        },
    ]

    for sensor in sensors:
        entry = entity_registry.async_get(sensor["entity_id"])
        assert entry is not None
        assert entry.unit_of_measurement == sensor.get("units")
