"""Basic checks for HomeKit select entities."""
from aiohomekit.model import Accessory
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from tests.components.homekit_controller.common import Helper, setup_test_component


def create_service_with_ecobee_mode(accessory: Accessory):
    """Define a thermostat with ecobee mode characteristics."""
    service = accessory.add_service(ServicesTypes.THERMOSTAT, add_required=True)

    current_mode = service.add_char(CharacteristicsTypes.VENDOR_ECOBEE_CURRENT_MODE)
    current_mode.value = 0
    current_mode.perms.append("ev")

    service.add_char(CharacteristicsTypes.VENDOR_ECOBEE_SET_HOLD_SCHEDULE)

    return service


async def test_read_current_mode(hass, utcnow):
    """Test that Ecobee mode can be correctly read and show as human readable text."""
    helper = await setup_test_component(hass, create_service_with_ecobee_mode)

    # Helper will be for the primary entity, which is the service. Make a helper for the sensor.
    ecobee_mode = Helper(
        hass,
        "select.testdevice_current_mode",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    state = await ecobee_mode.async_update(
        ServicesTypes.THERMOSTAT,
        {
            CharacteristicsTypes.VENDOR_ECOBEE_CURRENT_MODE: 0,
        },
    )
    assert state.state == "home"

    state = await ecobee_mode.async_update(
        ServicesTypes.THERMOSTAT,
        {
            CharacteristicsTypes.VENDOR_ECOBEE_CURRENT_MODE: 1,
        },
    )
    assert state.state == "sleep"

    state = await ecobee_mode.async_update(
        ServicesTypes.THERMOSTAT,
        {
            CharacteristicsTypes.VENDOR_ECOBEE_CURRENT_MODE: 2,
        },
    )
    assert state.state == "away"


async def test_write_current_mode(hass, utcnow):
    """Test can set a specific mode."""
    helper = await setup_test_component(hass, create_service_with_ecobee_mode)
    helper.accessory.services.first(service_type=ServicesTypes.THERMOSTAT)

    # Helper will be for the primary entity, which is the service. Make a helper for the sensor.
    current_mode = Helper(
        hass,
        "select.testdevice_current_mode",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.testdevice_current_mode", "option": "home"},
        blocking=True,
    )
    current_mode.async_assert_service_values(
        ServicesTypes.THERMOSTAT,
        {CharacteristicsTypes.VENDOR_ECOBEE_SET_HOLD_SCHEDULE: 0},
    )

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.testdevice_current_mode", "option": "sleep"},
        blocking=True,
    )
    current_mode.async_assert_service_values(
        ServicesTypes.THERMOSTAT,
        {CharacteristicsTypes.VENDOR_ECOBEE_SET_HOLD_SCHEDULE: 1},
    )

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.testdevice_current_mode", "option": "away"},
        blocking=True,
    )
    current_mode.async_assert_service_values(
        ServicesTypes.THERMOSTAT,
        {CharacteristicsTypes.VENDOR_ECOBEE_SET_HOLD_SCHEDULE: 2},
    )
