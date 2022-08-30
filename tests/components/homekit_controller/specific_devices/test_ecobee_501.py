"""Tests for Ecobee 501."""


from homeassistant.components.climate.const import (
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import STATE_ON

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_ecobee501_setup(hass):
    """Test that a Ecobee 501 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "ecobee_501.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="My ecobee",
            model="ECB501",
            manufacturer="ecobee Inc.",
            sw_version="4.7.340214",
            hw_version="",
            serial_number="123456789016",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="climate.my_ecobee",
                    friendly_name="My ecobee",
                    unique_id="homekit-123456789016-16",
                    supported_features=(
                        SUPPORT_TARGET_TEMPERATURE
                        | SUPPORT_TARGET_TEMPERATURE_RANGE
                        | SUPPORT_TARGET_HUMIDITY
                        | SUPPORT_FAN_MODE
                    ),
                    capabilities={
                        "hvac_modes": ["off", "heat", "cool", "heat_cool"],
                        "fan_modes": ["on", "auto"],
                        "min_temp": 7.2,
                        "max_temp": 33.3,
                        "min_humidity": 20,
                        "max_humidity": 50,
                    },
                    state="heat_cool",
                ),
                EntityTestInfo(
                    entity_id="binary_sensor.my_ecobee_occupancy",
                    friendly_name="My ecobee Occupancy",
                    unique_id="homekit-123456789016-57",
                    unit_of_measurement=None,
                    state=STATE_ON,
                ),
            ],
        ),
    )
