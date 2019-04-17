"""
Regression tests for Ecobee 3.

https://github.com/home-assistant/home-assistant/issues/15336
"""

from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_TARGET_HUMIDITY,
    SUPPORT_OPERATION_MODE)
from tests.components.homekit_controller.common import (
    device_config_changed, setup_accessories_from_file, setup_test_accessories,
    Helper
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
        SUPPORT_TARGET_TEMPERATURE | SUPPORT_TARGET_HUMIDITY |
        SUPPORT_OPERATION_MODE
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


async def test_ecobee3_add_sensors_at_runtime(hass):
    """Test that new sensors are automatically added."""
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # Set up a base Ecobee 3 with no additional sensors.
    # There shouldn't be any entities but climate visible.
    accessories = await setup_accessories_from_file(
        hass, 'ecobee3_no_sensors.json')
    await setup_test_accessories(hass, accessories)

    climate = entity_registry.async_get('climate.homew')
    assert climate.unique_id == 'homekit-123456789012-16'

    occ1 = entity_registry.async_get('binary_sensor.kitchen')
    assert occ1 is None

    occ2 = entity_registry.async_get('binary_sensor.porch')
    assert occ2 is None

    occ3 = entity_registry.async_get('binary_sensor.basement')
    assert occ3 is None

    # Now added 3 new sensors at runtime - sensors should appear and climate
    # shouldn't be duplicated.
    accessories = await setup_accessories_from_file(hass, 'ecobee3.json')
    await device_config_changed(hass, accessories)

    occ1 = entity_registry.async_get('binary_sensor.kitchen')
    assert occ1.unique_id == 'homekit-AB1C-56'

    occ2 = entity_registry.async_get('binary_sensor.porch')
    assert occ2.unique_id == 'homekit-AB2C-56'

    occ3 = entity_registry.async_get('binary_sensor.basement')
    assert occ3.unique_id == 'homekit-AB3C-56'
