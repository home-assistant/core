"""Make sure that a H.A.A. fan can be setup."""

from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_haa_fan_setup(hass):
    """Test that a H.A.A. fan can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "haa_fan.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    # Check that the switch entity is handled correctly

    entry = entity_registry.async_get("switch.haa_c718b3")
    assert entry.unique_id == "homekit-C718B3-2-8"

    helper = Helper(hass, "switch.haa_c718b3", pairing, accessories[0], config_entry)
    state = await helper.poll_and_get_state()
    assert state.attributes["friendly_name"] == "HAA-C718B3"

    device = device_registry.async_get(entry.device_id)
    assert device.manufacturer == "José A. Jiménez Campos"
    assert device.name == "HAA-C718B3"
    assert device.sw_version == "5.0.18"
    assert device.via_device_id is not None

    # Assert the fan is detected
    entry = entity_registry.async_get("fan.haa_c718b3")
    assert entry.unique_id == "homekit-C718B3-1-8"

    helper = Helper(
        hass,
        "fan.haa_c718b3",
        pairing,
        accessories[0],
        config_entry,
    )
    state = await helper.poll_and_get_state()
    assert state.attributes["friendly_name"] == "HAA-C718B3"
    assert round(state.attributes["percentage_step"], 2) == 33.33
