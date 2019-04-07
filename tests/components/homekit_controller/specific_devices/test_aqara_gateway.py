"""
Regression tests for Aqara Gateway V3.

https://github.com/home-assistant/home-assistant/issues/20957
"""

from homeassistant.components.light import SUPPORT_BRIGHTNESS, SUPPORT_COLOR
from tests.components.homekit_controller.common import (
    setup_accessories_from_file, setup_test_accessories, Helper
)


async def test_aqara_gateway_setup(hass):
    """Test that a Aqara Gateway can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(
        hass, 'aqara_gateway.json')
    pairing = await setup_test_accessories(hass, accessories)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # Check that the light is correctly found and set up
    alarm_id = "alarm_control_panel.aqara_hub_1563"
    alarm = entity_registry.async_get(alarm_id)
    assert alarm.unique_id == 'homekit-0000000123456789-66304'

    alarm_helper = Helper(
        hass, 'alarm_control_panel.aqara_hub_1563', pairing, accessories[0])
    alarm_state = await alarm_helper.poll_and_get_state()
    assert alarm_state.attributes['friendly_name'] == 'Aqara Hub-1563'

    # Check that the light is correctly found and set up
    light = entity_registry.async_get('light.aqara_hub_1563')
    assert light.unique_id == 'homekit-0000000123456789-65792'

    light_helper = Helper(
        hass, 'light.aqara_hub_1563', pairing, accessories[0])
    light_state = await light_helper.poll_and_get_state()
    assert light_state.attributes['friendly_name'] == 'Aqara Hub-1563'
    assert light_state.attributes['supported_features'] == (
        SUPPORT_BRIGHTNESS | SUPPORT_COLOR
    )
