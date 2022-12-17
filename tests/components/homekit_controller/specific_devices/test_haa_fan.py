"""Make sure that a H.A.A. fan can be setup."""

from homeassistant.components.fan import ATTR_PERCENTAGE, SUPPORT_SET_SPEED
from homeassistant.helpers.entity import EntityCategory

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_haa_fan_setup(hass):
    """Test that a H.A.A. fan can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "haa_fan.json")
    await setup_test_accessories(hass, accessories)

    haa_fan_state = hass.states.get("fan.haa_c718b3")
    attributes = haa_fan_state.attributes
    assert attributes[ATTR_PERCENTAGE] == 66

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="HAA-C718B3",
            model="RavenSystem HAA",
            manufacturer="José A. Jiménez Campos",
            sw_version="5.0.18",
            hw_version="",
            serial_number="C718B3-1",
            devices=[
                DeviceTestInfo(
                    name="HAA-C718B3",
                    model="RavenSystem HAA",
                    manufacturer="José A. Jiménez Campos",
                    sw_version="5.0.18",
                    hw_version="",
                    serial_number="C718B3-2",
                    unique_id="00:00:00:00:00:00:aid:2",
                    devices=[],
                    entities=[
                        EntityTestInfo(
                            entity_id="switch.haa_c718b3",
                            friendly_name="HAA-C718B3",
                            unique_id="homekit-C718B3-2-8",
                            state="off",
                        )
                    ],
                ),
            ],
            entities=[
                EntityTestInfo(
                    entity_id="fan.haa_c718b3",
                    friendly_name="HAA-C718B3",
                    unique_id="homekit-C718B3-1-8",
                    state="on",
                    supported_features=SUPPORT_SET_SPEED,
                    capabilities={
                        "preset_modes": None,
                    },
                ),
                EntityTestInfo(
                    entity_id="button.haa_c718b3_setup",
                    friendly_name="HAA-C718B3 Setup",
                    unique_id="homekit-C718B3-1-aid:1-sid:1010-cid:1012",
                    entity_category=EntityCategory.CONFIG,
                    state="unknown",
                ),
                EntityTestInfo(
                    entity_id="button.haa_c718b3_update",
                    friendly_name="HAA-C718B3 Update",
                    unique_id="homekit-C718B3-1-aid:1-sid:1010-cid:1011",
                    entity_category=EntityCategory.CONFIG,
                    state="unknown",
                ),
            ],
        ),
    )
