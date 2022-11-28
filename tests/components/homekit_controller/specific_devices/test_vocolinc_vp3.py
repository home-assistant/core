"""Make sure that existing VOCOlinc VP3 support isn't broken."""

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


async def test_vocolinc_vp3_setup(hass):
    """Test that a VOCOlinc VP3 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "vocolinc_vp3.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="VOCOlinc-VP3-123456",
            model="VP3",
            manufacturer="VOCOlinc",
            sw_version="1.101.2",
            hw_version="1.0.3",
            serial_number="EU0121203xxxxx07",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="switch.vocolinc_vp3_123456_outlet",
                    friendly_name="VOCOlinc-VP3-123456 Outlet",
                    unique_id="homekit-EU0121203xxxxx07-48",
                    state="on",
                ),
                EntityTestInfo(
                    entity_id="sensor.vocolinc_vp3_123456_power",
                    friendly_name="VOCOlinc-VP3-123456 Power",
                    unique_id="homekit-EU0121203xxxxx07-aid:1-sid:48-cid:97",
                    unit_of_measurement=POWER_WATT,
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    state="0",
                ),
            ],
        ),
    )
