"""
Regression tests for Aqara Gateway V3.

https://github.com/home-assistant/home-assistant/issues/20885
"""

from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE)
from tests.components.homekit_controller.common import (
    setup_accessories_from_file, setup_test_accessories, Helper
)


async def test_lennox_e30_setup(hass):
    """Test that a Lennox E30 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, 'lennox_e30.json')
    pairing = await setup_test_accessories(hass, accessories)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    climate = entity_registry.async_get('climate.lennox')
    assert climate.unique_id == 'homekit-XXXXXXXX-100'

    climate_helper = Helper(hass, 'climate.lennox', pairing, accessories[0])
    climate_state = await climate_helper.poll_and_get_state()
    assert climate_state.attributes['friendly_name'] == 'Lennox'
    assert climate_state.attributes['supported_features'] == (
        SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE
    )
