"""Make sure that existing RainMachine support isn't broken.

https://github.com/home-assistant/core/issues/31745
"""
from homeassistant.core import HomeAssistant

from ..common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_rainmachine_pro_8_setup(hass: HomeAssistant) -> None:
    """Test that a RainMachine can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "rainmachine-pro-8.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="RainMachine-00ce4a",
            model="SPK5 Pro",
            manufacturer="Green Electronics LLC",
            sw_version="1.0.4",
            hw_version="1",
            serial_number="00aa0000aa0a",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="switch.rainmachine_00ce4a",
                    friendly_name="RainMachine-00ce4a",
                    unique_id="00:00:00:00:00:00_1_512",
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="switch.rainmachine_00ce4a_2",
                    friendly_name="RainMachine-00ce4a",
                    unique_id="00:00:00:00:00:00_1_768",
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="switch.rainmachine_00ce4a_3",
                    friendly_name="RainMachine-00ce4a",
                    unique_id="00:00:00:00:00:00_1_1024",
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="switch.rainmachine_00ce4a_4",
                    friendly_name="RainMachine-00ce4a",
                    unique_id="00:00:00:00:00:00_1_1280",
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="switch.rainmachine_00ce4a_5",
                    friendly_name="RainMachine-00ce4a",
                    unique_id="00:00:00:00:00:00_1_1536",
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="switch.rainmachine_00ce4a_6",
                    friendly_name="RainMachine-00ce4a",
                    unique_id="00:00:00:00:00:00_1_1792",
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="switch.rainmachine_00ce4a_7",
                    friendly_name="RainMachine-00ce4a",
                    unique_id="00:00:00:00:00:00_1_2048",
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="switch.rainmachine_00ce4a_8",
                    friendly_name="RainMachine-00ce4a",
                    unique_id="00:00:00:00:00:00_1_2304",
                    state="off",
                ),
            ],
        ),
    )
