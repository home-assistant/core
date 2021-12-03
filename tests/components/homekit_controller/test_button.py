"""Basic checks for HomeKit button."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from tests.components.homekit_controller.common import Helper, setup_test_component


def create_switch_with_setup_button(accessory):
    """Define setup button characteristics."""
    service = accessory.add_service(ServicesTypes.OUTLET)

    setup = service.add_char(CharacteristicsTypes.Vendor.HAA_SETUP)

    setup.value = ""
    setup.format = "string"

    cur_state = service.add_char(CharacteristicsTypes.ON)
    cur_state.value = True

    return service


async def test_press_button(hass):
    """Test a switch service that has a button characteristic is correctly handled."""
    helper = await setup_test_component(hass, create_switch_with_setup_button)

    # Helper will be for the primary entity, which is the outlet. Make a helper for the button.
    energy_helper = Helper(
        hass,
        "button.testdevice_setup",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    outlet = energy_helper.accessory.services.first(service_type=ServicesTypes.OUTLET)
    setup = outlet[CharacteristicsTypes.Vendor.HAA_SETUP]

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.testdevice_setup"},
        blocking=True,
    )
    assert setup.value == "#HAA@trcmd"
