"""
Make sure that existing Koogeek SW2 is enumerated correctly.

This Koogeek device has a custom power sensor that extra handling.

It should have 2 entities - the actual switch and a sensor for power usage.
"""

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import POWER_WATT

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_koogeek_sw2_setup(hass):
    """Test that a Koogeek LS1 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "koogeek_sw2.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Koogeek-SW2-187A91",
            model="KH02CN",
            manufacturer="Koogeek",
            sw_version="1.0.3",
            hw_version="",
            serial_number="CNNT061751001372",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="switch.koogeek_sw2_187a91_switch_1",
                    friendly_name="Koogeek-SW2-187A91 Switch 1",
                    unique_id="homekit-CNNT061751001372-8",
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="switch.koogeek_sw2_187a91_switch_2",
                    friendly_name="Koogeek-SW2-187A91 Switch 2",
                    unique_id="homekit-CNNT061751001372-11",
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="sensor.koogeek_sw2_187a91_power",
                    friendly_name="Koogeek-SW2-187A91 Power",
                    unique_id="homekit-CNNT061751001372-aid:1-sid:14-cid:18",
                    unit_of_measurement=POWER_WATT,
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    state="0",
                ),
            ],
        ),
    )
