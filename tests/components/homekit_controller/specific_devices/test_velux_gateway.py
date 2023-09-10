"""Test against characteristics captured from a Velux Gateway.

https://github.com/home-assistant/core/issues/44314
"""
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant

from ..common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_velux_cover_setup(hass: HomeAssistant) -> None:
    """Test that a velux gateway can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "velux_gateway.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="VELUX Gateway",
            model="VELUX Gateway",
            manufacturer="VELUX",
            sw_version="70",
            hw_version="",
            serial_number="a1a11a1",
            devices=[
                DeviceTestInfo(
                    name="VELUX Window",
                    model="VELUX Window",
                    manufacturer="VELUX",
                    sw_version="48",
                    hw_version="",
                    serial_number="1111111a114a111a",
                    unique_id="00:00:00:00:00:00:aid:3",
                    devices=[],
                    entities=[
                        EntityTestInfo(
                            entity_id="cover.velux_window_roof_window",
                            friendly_name="VELUX Window Roof Window",
                            unique_id="00:00:00:00:00:00_3_8",
                            supported_features=CoverEntityFeature.CLOSE
                            | CoverEntityFeature.SET_POSITION
                            | CoverEntityFeature.OPEN,
                            state="closed",
                        ),
                    ],
                ),
                DeviceTestInfo(
                    name="VELUX Sensor",
                    model="VELUX Sensor",
                    manufacturer="VELUX",
                    sw_version="16",
                    hw_version="",
                    serial_number="a11b111",
                    unique_id="00:00:00:00:00:00:aid:2",
                    devices=[],
                    entities=[
                        EntityTestInfo(
                            entity_id="sensor.velux_sensor_temperature_sensor",
                            friendly_name="VELUX Sensor Temperature sensor",
                            capabilities={"state_class": SensorStateClass.MEASUREMENT},
                            unique_id="00:00:00:00:00:00_2_8",
                            unit_of_measurement=UnitOfTemperature.CELSIUS,
                            state="18.9",
                        ),
                        EntityTestInfo(
                            entity_id="sensor.velux_sensor_humidity_sensor",
                            friendly_name="VELUX Sensor Humidity sensor",
                            capabilities={"state_class": SensorStateClass.MEASUREMENT},
                            unique_id="00:00:00:00:00:00_2_11",
                            unit_of_measurement=PERCENTAGE,
                            state="58",
                        ),
                        EntityTestInfo(
                            entity_id="sensor.velux_sensor_carbon_dioxide_sensor",
                            friendly_name="VELUX Sensor Carbon Dioxide sensor",
                            capabilities={"state_class": SensorStateClass.MEASUREMENT},
                            unique_id="00:00:00:00:00:00_2_14",
                            unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                            state="400",
                        ),
                    ],
                ),
            ],
            entities=[],
        ),
    )
