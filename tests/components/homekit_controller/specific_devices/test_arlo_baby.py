"""Make sure that an Arlo Baby can be setup."""
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant

from ..common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_arlo_baby_setup(hass: HomeAssistant) -> None:
    """Test that an Arlo Baby can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "arlo_baby.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="ArloBabyA0",
            model="ABC1000",
            manufacturer="Netgear, Inc",
            sw_version="1.10.931",
            hw_version="",
            serial_number="00A0000000000",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="camera.arlobabya0",
                    unique_id="00:00:00:00:00:00_1",
                    friendly_name="ArloBabyA0",
                    state="idle",
                ),
                EntityTestInfo(
                    entity_id="binary_sensor.arlobabya0_motion",
                    unique_id="00:00:00:00:00:00_1_500",
                    friendly_name="ArloBabyA0 Motion",
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="sensor.arlobabya0_battery",
                    unique_id="00:00:00:00:00:00_1_700",
                    friendly_name="ArloBabyA0 Battery",
                    entity_category=EntityCategory.DIAGNOSTIC,
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=PERCENTAGE,
                    state="82",
                ),
                EntityTestInfo(
                    entity_id="sensor.arlobabya0_humidity",
                    unique_id="00:00:00:00:00:00_1_900",
                    friendly_name="ArloBabyA0 Humidity",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=PERCENTAGE,
                    state="60.099998",
                ),
                EntityTestInfo(
                    entity_id="sensor.arlobabya0_temperature",
                    unique_id="00:00:00:00:00:00_1_1000",
                    friendly_name="ArloBabyA0 Temperature",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=UnitOfTemperature.CELSIUS,
                    state="24.0",
                ),
                EntityTestInfo(
                    entity_id="sensor.arlobabya0_air_quality",
                    unique_id="00:00:00:00:00:00_1_800_802",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    friendly_name="ArloBabyA0 Air Quality",
                    state="1",
                ),
                EntityTestInfo(
                    entity_id="light.arlobabya0_nightlight",
                    unique_id="00:00:00:00:00:00_1_1100",
                    friendly_name="ArloBabyA0 Nightlight",
                    supported_features=0,
                    capabilities={"supported_color_modes": ["hs"]},
                    state="off",
                ),
            ],
        ),
    )
