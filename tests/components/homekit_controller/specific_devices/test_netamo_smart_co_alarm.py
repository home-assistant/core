"""Regression tests for Netamo Smart CO Alarm.

https://github.com/home-assistant/core/issues/78903
"""
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant

from ..common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_netamo_smart_co_alarm_setup(hass: HomeAssistant) -> None:
    """Test that a Netamo Smart CO Alarm can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "netamo_smart_co_alarm.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Smart CO Alarm",
            model="Smart CO Alarm",
            manufacturer="Netatmo",
            sw_version="1.0.3",
            hw_version="0",
            serial_number="1234",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="binary_sensor.smart_co_alarm_carbon_monoxide_sensor",
                    friendly_name="Smart CO Alarm Carbon Monoxide Sensor",
                    unique_id="00:00:00:00:00:00_1_22",
                    state="off",
                ),
                EntityTestInfo(
                    entity_id="binary_sensor.smart_co_alarm_low_battery",
                    friendly_name="Smart CO Alarm Low Battery",
                    entity_category=EntityCategory.DIAGNOSTIC,
                    unique_id="00:00:00:00:00:00_1_36",
                    state="off",
                ),
            ],
        ),
    )
