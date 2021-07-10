"""
Test against characteristics captured from a SIMPLEconnect Fan.

https://github.com/home-assistant/core/issues/26180
"""

from homeassistant.components.fan import SUPPORT_DIRECTION, SUPPORT_SET_SPEED
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_simpleconnect_fan_setup(hass):
    """Test that a SIMPLEconnect fan can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "simpleconnect_fan.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)

    # Check that the fan is correctly found and set up
    fan_id = "fan.simpleconnect_fan_06f674"
    fan = entity_registry.async_get(fan_id)
    assert fan.unique_id == "homekit-1234567890abcd-8"

    fan_helper = Helper(
        hass,
        "fan.simpleconnect_fan_06f674",
        pairing,
        accessories[0],
        config_entry,
    )

    fan_state = await fan_helper.poll_and_get_state()
    assert fan_state.attributes["friendly_name"] == "SIMPLEconnect Fan-06F674"
    assert fan_state.state == "off"
    assert fan_state.attributes["supported_features"] == (
        SUPPORT_DIRECTION | SUPPORT_SET_SPEED
    )

    device_registry = dr.async_get(hass)

    device = device_registry.async_get(fan.device_id)
    assert device.manufacturer == "Hunter Fan"
    assert device.name == "SIMPLEconnect Fan-06F674"
    assert device.model == "SIMPLEconnect"
    assert device.sw_version == ""
    assert device.via_device_id is None
