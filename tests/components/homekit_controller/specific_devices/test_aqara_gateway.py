"""
Regression tests for Aqara Gateway V3.

https://github.com/home-assistant/core/issues/20957
"""

from homeassistant.components.light import SUPPORT_BRIGHTNESS, SUPPORT_COLOR
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_aqara_gateway_setup(hass):
    """Test that a Aqara Gateway can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "aqara_gateway.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)

    # Check that the light is correctly found and set up
    alarm_id = "alarm_control_panel.aqara_hub_1563"
    alarm = entity_registry.async_get(alarm_id)
    assert alarm.unique_id == "homekit-0000000123456789-66304"

    alarm_helper = Helper(
        hass,
        "alarm_control_panel.aqara_hub_1563",
        pairing,
        accessories[0],
        config_entry,
    )
    alarm_state = await alarm_helper.poll_and_get_state()
    assert alarm_state.attributes["friendly_name"] == "Aqara Hub-1563"

    # Check that the light is correctly found and set up
    light = entity_registry.async_get("light.aqara_hub_1563")
    assert light.unique_id == "homekit-0000000123456789-65792"

    light_helper = Helper(
        hass, "light.aqara_hub_1563", pairing, accessories[0], config_entry
    )
    light_state = await light_helper.poll_and_get_state()
    assert light_state.attributes["friendly_name"] == "Aqara Hub-1563"
    assert light_state.attributes["supported_features"] == (
        SUPPORT_BRIGHTNESS | SUPPORT_COLOR
    )

    device_registry = dr.async_get(hass)

    # All the entities are services of the same accessory
    # So it looks at the protocol like a single physical device
    assert alarm.device_id == light.device_id

    device = device_registry.async_get(light.device_id)
    assert device.manufacturer == "Aqara"
    assert device.name == "Aqara Hub-1563"
    assert device.model == "ZHWA11LM"
    assert device.sw_version == "1.4.7"
    assert device.via_device_id is None
