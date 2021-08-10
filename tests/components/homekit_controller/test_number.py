"""Basic checks for HomeKit sensor."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from tests.components.homekit_controller.common import Helper, setup_test_component


def create_switch_with_spray_level(accessory):
    """Define battery level characteristics."""
    service = accessory.add_service(ServicesTypes.OUTLET)

    spray_level = service.add_char(
        CharacteristicsTypes.Vendor.VOCOLINC_HUMIDIFIER_SPRAY_LEVEL
    )

    spray_level.value = 1
    spray_level.minStep = 1
    spray_level.minValue = 1
    spray_level.maxValue = 5
    spray_level.format = "float"

    cur_state = service.add_char(CharacteristicsTypes.ON)
    cur_state.value = True

    return service


async def test_read_number(hass, utcnow):
    """Test a switch service that has a sensor characteristic is correctly handled."""
    helper = await setup_test_component(hass, create_switch_with_spray_level)
    outlet = helper.accessory.services.first(service_type=ServicesTypes.OUTLET)

    # Helper will be for the primary entity, which is the outlet. Make a helper for the sensor.
    energy_helper = Helper(
        hass,
        "number.testdevice",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    outlet = energy_helper.accessory.services.first(service_type=ServicesTypes.OUTLET)
    spray_level = outlet[CharacteristicsTypes.Vendor.VOCOLINC_HUMIDIFIER_SPRAY_LEVEL]

    state = await energy_helper.poll_and_get_state()
    assert state.state == "1"
    assert state.attributes["step"] == 1
    assert state.attributes["min"] == 1
    assert state.attributes["max"] == 5

    spray_level.value = 5
    state = await energy_helper.poll_and_get_state()
    assert state.state == "5"


async def test_write_number(hass, utcnow):
    """Test a switch service that has a sensor characteristic is correctly handled."""
    helper = await setup_test_component(hass, create_switch_with_spray_level)
    outlet = helper.accessory.services.first(service_type=ServicesTypes.OUTLET)

    # Helper will be for the primary entity, which is the outlet. Make a helper for the sensor.
    energy_helper = Helper(
        hass,
        "number.testdevice",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    outlet = energy_helper.accessory.services.first(service_type=ServicesTypes.OUTLET)
    spray_level = outlet[CharacteristicsTypes.Vendor.VOCOLINC_HUMIDIFIER_SPRAY_LEVEL]

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.testdevice", "value": 5},
        blocking=True,
    )
    assert spray_level.value == 5

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.testdevice", "value": 3},
        blocking=True,
    )
    assert spray_level.value == 3
