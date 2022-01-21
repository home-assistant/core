"""Make sure that existing VOCOlinc VP3 support isn't broken."""

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import POWER_WATT

from tests.components.homekit_controller.common import (
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_koogeek_p1eu_setup(hass):
    """Test that a VOCOlinc VP3 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "vocolinc_vp3.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id="00:00:00:00:00:00",
            name="VOCOlinc-VP3-123456",
            model="VP3",
            manufacturer="VOCOlinc",
            sw_version="1.101.2",
            hw_version="",
            serial_number="EU0121203xxxxx07",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="switch.vocolinc_vp3_123456",
                    friendly_name="VOCOlinc-VP3-123456",
                    unique_id="homekit-EU0121203xxxxx07-7",
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="sensor.vocolinc_vp3_123456_real_time_energy",
                    friendly_name="VOCOlinc-VP3-123456 - Real Time Energy",
                    unique_id="homekit-EU0121203xxxxx07-aid:1-sid:21-cid:22",
                    unit_of_measurement=POWER_WATT,
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    state="5",
                ),
            ],
        ),
    )
