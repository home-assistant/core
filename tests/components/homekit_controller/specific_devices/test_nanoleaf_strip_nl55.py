"""Make sure that Nanoleaf NL55 works with BLE."""

from homeassistant.helpers.entity import EntityCategory

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)

LIGHT_ON = ("lightbulb", "on")


async def test_nanoleaf_nl55_setup(hass):
    """Test that a Nanoleaf NL55 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "nanoleaf_strip_nl55.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Koogeek-LS1-20833F",
            model="LS1",
            manufacturer="Koogeek",
            sw_version="2.2.15",
            hw_version="",
            serial_number="AAAA011111111111",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="light.koogeek_ls1_20833f_light_strip",
                    friendly_name="Koogeek-LS1-20833F Light Strip",
                    unique_id="homekit-AAAA011111111111-7",
                    supported_features=0,
                    capabilities={"supported_color_modes": ["hs"]},
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="button.koogeek_ls1_20833f_identify",
                    friendly_name="Koogeek-LS1-20833F Identify",
                    unique_id="homekit-AAAA011111111111-aid:1-sid:1-cid:6",
                    entity_category=EntityCategory.DIAGNOSTIC,
                    state="unknown",
                ),
            ],
        ),
    )
