"""Basic checks for HomeKit button."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from tests.components.homekit_controller.common import Helper, setup_test_component


def create_switch_with_setup_button(accessory):
    """Define setup button characteristics."""
    service = accessory.add_service(ServicesTypes.OUTLET)

    setup = service.add_char(CharacteristicsTypes.VENDOR_HAA_SETUP)

    setup.value = ""
    setup.format = "string"

    cur_state = service.add_char(CharacteristicsTypes.ON)
    cur_state.value = True

    return service


def create_switch_with_ecobee_clear_hold_button(accessory):
    """Define setup button characteristics."""
    service = accessory.add_service(ServicesTypes.OUTLET)

    setup = service.add_char(CharacteristicsTypes.VENDOR_ECOBEE_CLEAR_HOLD)

    setup.value = ""
    setup.format = "string"

    cur_state = service.add_char(CharacteristicsTypes.ON)
    cur_state.value = True

    return service


async def test_press_button(hass):
    """Test a switch service that has a button characteristic is correctly handled."""
    helper = await setup_test_component(hass, create_switch_with_setup_button)

    # Helper will be for the primary entity, which is the outlet. Make a helper for the button.
    button = Helper(
        hass,
        "button.testdevice_setup",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.testdevice_setup"},
        blocking=True,
    )
    button.async_assert_service_values(
        ServicesTypes.OUTLET,
        {
            CharacteristicsTypes.VENDOR_HAA_SETUP: "#HAA@trcmd",
        },
    )


async def test_ecobee_clear_hold_press_button(hass):
    """Test ecobee clear hold button characteristic is correctly handled."""
    helper = await setup_test_component(
        hass, create_switch_with_ecobee_clear_hold_button
    )

    # Helper will be for the primary entity, which is the outlet. Make a helper for the button.
    clear_hold = Helper(
        hass,
        "button.testdevice_clear_hold",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.testdevice_clear_hold"},
        blocking=True,
    )
    clear_hold.async_assert_service_values(
        ServicesTypes.OUTLET,
        {
            CharacteristicsTypes.VENDOR_ECOBEE_CLEAR_HOLD: True,
        },
    )
