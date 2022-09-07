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
            name="Nanoleaf Strip 3B32",
            model="NL55",
            manufacturer="Nanoleaf",
            sw_version="1.4.40",
            hw_version="1.2.4",
            serial_number="AAAA011111111111",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="light.nanoleaf_strip_3b32_nanoleaf_light_strip",
                    friendly_name="Nanoleaf Strip 3B32 Nanoleaf Light Strip",
                    unique_id="homekit-AAAA011111111111-19",
                    supported_features=0,
                    capabilities={
                        "max_mireds": 470,
                        "min_mireds": 153,
                        "supported_color_modes": ["color_temp", "hs"],
                    },
                    state="on",
                ),
                EntityTestInfo(
                    entity_id="button.nanoleaf_strip_3b32_identify",
                    friendly_name="Nanoleaf Strip 3B32 Identify",
                    unique_id="homekit-AAAA011111111111-aid:1-sid:1-cid:2",
                    entity_category=EntityCategory.DIAGNOSTIC,
                    state="unknown",
                ),
                EntityTestInfo(
                    entity_id="sensor.nanoleaf_strip_3b32_thread_capabilities",
                    friendly_name="Nanoleaf Strip 3B32 Thread Capabilities",
                    unique_id="homekit-AAAA011111111111-aid:1-sid:31-cid:115",
                    entity_category=EntityCategory.DIAGNOSTIC,
                    state="border_router_capable",
                ),
                EntityTestInfo(
                    entity_id="sensor.nanoleaf_strip_3b32_thread_status",
                    friendly_name="Nanoleaf Strip 3B32 Thread Status",
                    unique_id="homekit-AAAA011111111111-aid:1-sid:31-cid:117",
                    entity_category=EntityCategory.DIAGNOSTIC,
                    state="border_router",
                ),
            ],
        ),
    )
