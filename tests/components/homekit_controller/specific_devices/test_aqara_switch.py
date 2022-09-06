"""
Regression tests for Aqara AR004.

This device has a non-standard programmable stateless switch service that has a
service-label-index despite not being linked to a service-label.

https://github.com/home-assistant/core/pull/39090
"""

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    DeviceTriggerInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_aqara_switch_setup(hass):
    """Test that a Aqara Switch can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "aqara_switch.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Programmable Switch",
            model="AR004",
            manufacturer="Aqara",
            sw_version="9",
            hw_version="1.0",
            serial_number="111a1111a1a111",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="sensor.programmable_switch_battery_sensor",
                    friendly_name="Programmable Switch Battery Sensor",
                    unique_id="homekit-111a1111a1a111-5",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                    unit_of_measurement=PERCENTAGE,
                    state="100",
                ),
            ],
            stateless_triggers=[
                DeviceTriggerInfo(type="button1", subtype="single_press"),
                DeviceTriggerInfo(type="button1", subtype="double_press"),
                DeviceTriggerInfo(type="button1", subtype="long_press"),
            ],
        ),
    )
