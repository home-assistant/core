"""
Regression tests for Ecobee occupancy.

https://github.com/home-assistant/core/issues/31827
"""

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_ecobee_occupancy_setup(hass):
    """Test that an Ecbobee occupancy sensor be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "ecobee_occupancy.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Master Fan",
            model="ecobee Switch+",
            manufacturer="ecobee Inc.",
            sw_version="4.5.130201",
            hw_version="",
            serial_number="111111111111",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="binary_sensor.master_fan",
                    friendly_name="Master Fan",
                    unique_id="homekit-111111111111-56",
                    state="off",
                ),
            ],
        ),
    )
