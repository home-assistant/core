"""Make sure that Mysa Living is enumerated properly."""
from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant

from ..common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_mysa_living_setup(hass: HomeAssistant) -> None:
    """Test that the accessory can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "mysa_living.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Mysa-85dda9",
            model="v1",
            manufacturer="Empowered Homes Inc.",
            sw_version="2.8.1",
            hw_version="",
            serial_number="AAAAAAA000",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="climate.mysa_85dda9_thermostat",
                    friendly_name="Mysa-85dda9 Thermostat",
                    unique_id="00:00:00:00:00:00_1_20",
                    supported_features=ClimateEntityFeature.TARGET_TEMPERATURE,
                    capabilities={
                        "hvac_modes": ["off", "heat", "cool", "heat_cool"],
                        "max_temp": 35,
                        "min_temp": 7,
                    },
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="sensor.mysa_85dda9_current_humidity",
                    friendly_name="Mysa-85dda9 Current Humidity",
                    unique_id="00:00:00:00:00:00_1_20_27",
                    unit_of_measurement=PERCENTAGE,
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    state="40",
                ),
                EntityTestInfo(
                    entity_id="sensor.mysa_85dda9_current_temperature",
                    friendly_name="Mysa-85dda9 Current Temperature",
                    unique_id="00:00:00:00:00:00_1_20_25",
                    unit_of_measurement=UnitOfTemperature.CELSIUS,
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    state="24.1",
                ),
                EntityTestInfo(
                    entity_id="light.mysa_85dda9_display",
                    friendly_name="Mysa-85dda9 Display",
                    unique_id="00:00:00:00:00:00_1_40",
                    supported_features=0,
                    capabilities={"supported_color_modes": ["brightness"]},
                    state="off",
                ),
            ],
        ),
    )
