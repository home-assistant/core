"""
Regression tests for Ecobee 3.

https://github.com/home-assistant/home-assistant/issues/15336
"""

from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE)
from tests.components.homekit_controller.common import (
    setup_accessories_from_file, setup_test_accessories, Helper
)


async def test_ecobee3_setup(hass):
    """Test that a Ecbobee 3 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, 'ecobee3.json')
    pairing = await setup_test_accessories(hass, accessories)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    climate = entity_registry.async_get('climate.homew')
    assert climate.unique_id == 'homekit-123456789012-16'

    climate_helper = Helper(hass, 'climate.homew', pairing, accessories[0])
    climate_state = await climate_helper.poll_and_get_state()
    assert climate_state.attributes['friendly_name'] == 'HomeW'
    assert climate_state.attributes['supported_features'] == (
        SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE
    )

    occ1 = entity_registry.async_get('binary_sensor.kitchen')
    assert occ1.unique_id == 'homekit-AB1C-56'

    occ1_helper = Helper(
        hass, 'binary_sensor.kitchen', pairing, accessories[0])
    occ1_state = await occ1_helper.poll_and_get_state()
    assert occ1_state.attributes['friendly_name'] == 'Kitchen'

    occ2 = entity_registry.async_get('binary_sensor.porch')
    assert occ2.unique_id == 'homekit-AB2C-56'

    occ3 = entity_registry.async_get('binary_sensor.basement')
    assert occ3.unique_id == 'homekit-AB3C-56'
