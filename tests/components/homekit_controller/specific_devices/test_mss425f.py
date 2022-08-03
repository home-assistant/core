"""Tests for the Meross MSS425f power strip."""


from homeassistant.const import STATE_ON, STATE_UNKNOWN
from homeassistant.helpers.entity import EntityCategory

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_meross_mss425f_setup(hass):
    """Test that a MSS425f can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "mss425f.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="MSS425F-15cc",
            model="MSS425F",
            manufacturer="Meross",
            sw_version="4.2.3",
            hw_version="4.0.0",
            serial_number="HH41234",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="button.mss425f_15cc_identify",
                    friendly_name="MSS425F-15cc Identify",
                    unique_id="homekit-HH41234-aid:1-sid:1-cid:2",
                    entity_category=EntityCategory.DIAGNOSTIC,
                    state=STATE_UNKNOWN,
                ),
                EntityTestInfo(
                    entity_id="switch.mss425f_15cc_outlet_1",
                    friendly_name="MSS425F-15cc Outlet-1",
                    unique_id="homekit-HH41234-12",
                    state=STATE_ON,
                ),
                EntityTestInfo(
                    entity_id="switch.mss425f_15cc_outlet_2",
                    friendly_name="MSS425F-15cc Outlet-2",
                    unique_id="homekit-HH41234-15",
                    state=STATE_ON,
                ),
                EntityTestInfo(
                    entity_id="switch.mss425f_15cc_outlet_3",
                    friendly_name="MSS425F-15cc Outlet-3",
                    unique_id="homekit-HH41234-18",
                    state=STATE_ON,
                ),
                EntityTestInfo(
                    entity_id="switch.mss425f_15cc_outlet_4",
                    friendly_name="MSS425F-15cc Outlet-4",
                    unique_id="homekit-HH41234-21",
                    state=STATE_ON,
                ),
                EntityTestInfo(
                    entity_id="switch.mss425f_15cc_usb",
                    friendly_name="MSS425F-15cc USB",
                    unique_id="homekit-HH41234-24",
                    state=STATE_ON,
                ),
            ],
        ),
    )
