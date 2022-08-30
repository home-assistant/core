"""Make sure that Vocolinc Flowerbud is enumerated properly."""

from homeassistant.components.humidifier.const import SUPPORT_MODES
from homeassistant.components.number import NumberMode
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.entity import EntityCategory

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_vocolinc_flowerbud_setup(hass):
    """Test that a Vocolinc Flowerbud can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "vocolinc_flowerbud.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="VOCOlinc-Flowerbud-0d324b",
            model="Flowerbud",
            manufacturer="VOCOlinc",
            sw_version="3.121.2",
            hw_version="0.1",
            serial_number="AM01121849000327",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="humidifier.vocolinc_flowerbud_0d324b",
                    friendly_name="VOCOlinc-Flowerbud-0d324b",
                    unique_id="homekit-AM01121849000327-30",
                    supported_features=SUPPORT_MODES,
                    capabilities={
                        "available_modes": ["normal", "auto"],
                        "max_humidity": 100.0,
                        "min_humidity": 0.0,
                    },
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="light.vocolinc_flowerbud_0d324b_mood_light",
                    friendly_name="VOCOlinc-Flowerbud-0d324b Mood Light",
                    unique_id="homekit-AM01121849000327-9",
                    supported_features=0,
                    capabilities={"supported_color_modes": ["hs"]},
                    state="on",
                ),
                EntityTestInfo(
                    entity_id="number.vocolinc_flowerbud_0d324b_spray_quantity",
                    friendly_name="VOCOlinc-Flowerbud-0d324b Spray Quantity",
                    unique_id="homekit-AM01121849000327-aid:1-sid:30-cid:38",
                    capabilities={
                        "max": 5,
                        "min": 1,
                        "mode": NumberMode.AUTO,
                        "step": 1,
                    },
                    state="5",
                    entity_category=EntityCategory.CONFIG,
                ),
                EntityTestInfo(
                    entity_id="sensor.vocolinc_flowerbud_0d324b_current_humidity",
                    friendly_name="VOCOlinc-Flowerbud-0d324b Current Humidity",
                    unique_id="homekit-AM01121849000327-aid:1-sid:30-cid:33",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=PERCENTAGE,
                    state="45.0",
                ),
            ],
        ),
    )
