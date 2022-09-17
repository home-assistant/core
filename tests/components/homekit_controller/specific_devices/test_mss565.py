"""Tests for the Meross MSS565 wall switch."""


from homeassistant.const import STATE_ON

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_meross_mss565_setup(hass):
    """Test that a MSS565 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "mss565.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="MSS565-28da",
            model="MSS565",
            manufacturer="Meross",
            sw_version="4.1.9",
            hw_version="4.0.0",
            serial_number="BB1121",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="light.mss565_28da_dimmer_switch",
                    friendly_name="MSS565-28da Dimmer Switch",
                    unique_id="homekit-BB1121-12",
                    capabilities={"supported_color_modes": ["brightness"]},
                    state=STATE_ON,
                ),
            ],
        ),
    )
