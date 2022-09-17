"""
Test against characteristics captured from a Velux Gateway.

https://github.com/home-assistant/core/issues/44314
"""

from homeassistant.components.cover import (
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
)
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    TEMP_CELSIUS,
)

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_velux_cover_setup(hass):
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
                            unique_id="homekit-1111111a114a111a-8",
                            supported_features=SUPPORT_CLOSE
                            | SUPPORT_SET_POSITION
                            | SUPPORT_OPEN,
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
                            unique_id="homekit-a11b111-8",
                            unit_of_measurement=TEMP_CELSIUS,
                            state="18.9",
                        ),
                        EntityTestInfo(
                            entity_id="sensor.velux_sensor_humidity_sensor",
                            friendly_name="VELUX Sensor Humidity sensor",
                            capabilities={"state_class": SensorStateClass.MEASUREMENT},
                            unique_id="homekit-a11b111-11",
                            unit_of_measurement=PERCENTAGE,
                            state="58",
                        ),
                        EntityTestInfo(
                            entity_id="sensor.velux_sensor_carbon_dioxide_sensor",
                            friendly_name="VELUX Sensor Carbon Dioxide sensor",
                            capabilities={"state_class": SensorStateClass.MEASUREMENT},
                            unique_id="homekit-a11b111-14",
                            unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                            state="400",
                        ),
                    ],
                ),
            ],
            entities=[],
        ),
    )
