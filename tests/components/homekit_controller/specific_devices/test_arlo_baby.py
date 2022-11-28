"""Make sure that an Arlo Baby can be setup."""

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_arlo_baby_setup(hass):
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
                    unique_id="homekit-00A0000000000-aid:1",
                    friendly_name="ArloBabyA0",
                    state="idle",
                ),
                EntityTestInfo(
                    entity_id="binary_sensor.arlobabya0_motion",
                    unique_id="homekit-00A0000000000-500",
                    friendly_name="ArloBabyA0 Motion",
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="sensor.arlobabya0_battery",
                    unique_id="homekit-00A0000000000-700",
                    friendly_name="ArloBabyA0 Battery",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=PERCENTAGE,
                    state="82",
                ),
                EntityTestInfo(
                    entity_id="sensor.arlobabya0_humidity",
                    unique_id="homekit-00A0000000000-900",
                    friendly_name="ArloBabyA0 Humidity",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=PERCENTAGE,
                    state="60.099998",
                ),
                EntityTestInfo(
                    entity_id="sensor.arlobabya0_temperature",
                    unique_id="homekit-00A0000000000-1000",
                    friendly_name="ArloBabyA0 Temperature",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=TEMP_CELSIUS,
                    state="24.0",
                ),
                EntityTestInfo(
                    entity_id="sensor.arlobabya0_air_quality",
                    unique_id="homekit-00A0000000000-aid:1-sid:800-cid:802",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    friendly_name="ArloBabyA0 Air Quality",
                    state="1",
                ),
                EntityTestInfo(
                    entity_id="light.arlobabya0_nightlight",
                    unique_id="homekit-00A0000000000-1100",
                    friendly_name="ArloBabyA0 Nightlight",
                    supported_features=0,
                    capabilities={"supported_color_modes": ["hs"]},
                    state="off",
                ),
            ],
        ),
    )
