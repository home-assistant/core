"""Make sure that existing Koogeek P1EU support isn't broken."""
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import POWER_WATT
from homeassistant.core import HomeAssistant

from ..common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_koogeek_p1eu_setup(hass: HomeAssistant) -> None:
    """Test that a Koogeek P1EU can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "koogeek_p1eu.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Koogeek-P1-A00AA0",
            model="P1EU",
            manufacturer="Koogeek",
            sw_version="2.3.7",
            hw_version="",
            serial_number="EUCP03190xxxxx48",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="switch.koogeek_p1_a00aa0_outlet",
                    friendly_name="Koogeek-P1-A00AA0 outlet",
                    unique_id="00:00:00:00:00:00_1_7",
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="sensor.koogeek_p1_a00aa0_power",
                    friendly_name="Koogeek-P1-A00AA0 Power",
                    unique_id="00:00:00:00:00:00_1_21_22",
                    unit_of_measurement=POWER_WATT,
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    state="5",
                ),
            ],
        ),
    )
