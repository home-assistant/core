"""Basic checks for HomeKit select entities."""
from aiohomekit.model import Accessory
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from tests.components.homekit_controller.common import Helper, setup_test_component


def create_service_with_ecobee_mode(accessory: Accessory):
    """Define a thermostat with ecobee mode characteristics."""
    service = accessory.add_service(ServicesTypes.THERMOSTAT, add_required=True)

    current_mode = service.add_char(CharacteristicsTypes.Vendor.ECOBEE_CURRENT_MODE)
    current_mode.value = 0

    service.add_char(CharacteristicsTypes.Vendor.ECOBEE_SET_HOLD_SCHEDULE)

    return service


async def test_read_current_mode(hass, utcnow):
    """Test that Ecobee mode can be correctly read and show as human readable text."""
    helper = await setup_test_component(hass, create_service_with_ecobee_mode)
    service = helper.accessory.services.first(service_type=ServicesTypes.THERMOSTAT)

    # Helper will be for the primary entity, which is the service. Make a helper for the sensor.
    energy_helper = Helper(
        hass,
        "select.testdevice_current_mode",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    mode = service[CharacteristicsTypes.Vendor.ECOBEE_CURRENT_MODE]

    state = await energy_helper.poll_and_get_state()
    assert state.state == "home"

    mode.value = 1
    state = await energy_helper.poll_and_get_state()
    assert state.state == "sleep"

    mode.value = 2
    state = await energy_helper.poll_and_get_state()
    assert state.state == "away"


async def test_write_current_mode(hass, utcnow):
    """Test can set a specific mode."""
    helper = await setup_test_component(hass, create_service_with_ecobee_mode)
    service = helper.accessory.services.first(service_type=ServicesTypes.THERMOSTAT)

    # Helper will be for the primary entity, which is the service. Make a helper for the sensor.
    energy_helper = Helper(
        hass,
        "select.testdevice_current_mode",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    service = energy_helper.accessory.services.first(
        service_type=ServicesTypes.THERMOSTAT
    )
    mode = service[CharacteristicsTypes.Vendor.ECOBEE_SET_HOLD_SCHEDULE]

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.testdevice_current_mode", "option": "home"},
        blocking=True,
    )
    assert mode.value == 0

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.testdevice_current_mode", "option": "sleep"},
        blocking=True,
    )
    assert mode.value == 1

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.testdevice_current_mode", "option": "away"},
        blocking=True,
    )
    assert mode.value == 2
