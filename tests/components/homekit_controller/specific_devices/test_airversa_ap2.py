"""Tests for Airversa AP2 Air Purifier."""
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from ..common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_airversa_ap2_setup(hass: HomeAssistant) -> None:
    """Test that an Ecbobee occupancy sensor be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "airversa_ap2.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Airversa AP2 1808",
            model="AP2",
            manufacturer="Sleekpoint Innovations",
            sw_version="0.8.16",
            hw_version="0.1",
            serial_number="1234",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="switch.airversa_ap2_1808_lock_physical_controls",
                    friendly_name="Airversa AP2 1808 Lock Physical Controls",
                    unique_id="00:00:00:00:00:00_1_32832_32839",
                    entity_category=EntityCategory.CONFIG,
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="switch.airversa_ap2_1808_mute",
                    friendly_name="Airversa AP2 1808 Mute",
                    unique_id="00:00:00:00:00:00_1_32832_32843",
                    entity_category=EntityCategory.CONFIG,
                    state="on",
                ),
                EntityTestInfo(
                    entity_id="switch.airversa_ap2_1808_sleep_mode",
                    friendly_name="Airversa AP2 1808 Sleep Mode",
                    unique_id="00:00:00:00:00:00_1_32832_32842",
                    entity_category=EntityCategory.CONFIG,
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="sensor.airversa_ap2_1808_air_quality",
                    friendly_name="Airversa AP2 1808 Air Quality",
                    unique_id="00:00:00:00:00:00_1_2576_2579",
                    state="1",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                ),
                EntityTestInfo(
                    entity_id="sensor.airversa_ap2_1808_filter_life",
                    friendly_name="Airversa AP2 1808 Filter Life",
                    unique_id="00:00:00:00:00:00_1_32896_32900",
                    state="100.0",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=PERCENTAGE,
                ),
                EntityTestInfo(
                    entity_id="sensor.airversa_ap2_1808_pm2_5_density",
                    friendly_name="Airversa AP2 1808 PM2.5 Density",
                    unique_id="00:00:00:00:00:00_1_2576_2580",
                    state="3.0",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                ),
                EntityTestInfo(
                    entity_id="sensor.airversa_ap2_1808_thread_capabilities",
                    friendly_name="Airversa AP2 1808 Thread Capabilities",
                    unique_id="00:00:00:00:00:00_1_112_115",
                    state="router_eligible",
                    entity_category=EntityCategory.DIAGNOSTIC,
                    capabilities={
                        "options": [
                            "border_router_capable",
                            "full",
                            "minimal",
                            "none",
                            "router_eligible",
                            "sleepy",
                        ]
                    },
                ),
                EntityTestInfo(
                    entity_id="sensor.airversa_ap2_1808_thread_status",
                    friendly_name="Airversa AP2 1808 Thread Status",
                    unique_id="00:00:00:00:00:00_1_112_117",
                    state="router",
                    entity_category=EntityCategory.DIAGNOSTIC,
                    capabilities={
                        "options": [
                            "border_router",
                            "child",
                            "detached",
                            "disabled",
                            "joining",
                            "leader",
                            "router",
                        ]
                    },
                ),
                EntityTestInfo(
                    entity_id="button.airversa_ap2_1808_identify",
                    friendly_name="Airversa AP2 1808 Identify",
                    unique_id="00:00:00:00:00:00_1_1_2",
                    entity_category=EntityCategory.DIAGNOSTIC,
                    state="unknown",
                ),
            ],
        ),
    )
