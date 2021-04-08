"""
Regression tests for Ecobee occupancy.

https://github.com/home-assistant/core/issues/31827
"""

from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_ecobee_occupancy_setup(hass):
    """Test that an Ecbobee occupancy sensor be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "ecobee_occupancy.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)

    sensor = entity_registry.async_get("binary_sensor.master_fan")
    assert sensor.unique_id == "homekit-111111111111-56"

    sensor_helper = Helper(
        hass, "binary_sensor.master_fan", pairing, accessories[0], config_entry
    )
    sensor_state = await sensor_helper.poll_and_get_state()
    assert sensor_state.attributes["friendly_name"] == "Master Fan"

    device_registry = dr.async_get(hass)

    device = device_registry.async_get(sensor.device_id)
    assert device.manufacturer == "ecobee Inc."
    assert device.name == "Master Fan"
    assert device.model == "ecobee Switch+"
    assert device.sw_version == "4.5.130201"
    assert device.via_device_id is None
