"""Regression tests for Netamo Healthy Home Coach.

https://github.com/home-assistant/core/issues/73360
"""
from homeassistant.components.sensor import SensorStateClass
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
    accessories = await setup_accessories_from_file(hass, "netatmo_home_coach.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Healthy Home Coach",
            model="Healthy Home Coach",
            manufacturer="Netatmo",
            sw_version="59",
            hw_version="",
            serial_number="1234",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="sensor.healthy_home_coach_noise",
                    friendly_name="Healthy Home Coach Noise",
                    unique_id="00:00:00:00:00:00_1_20_21",
                    state="0",
                    unit_of_measurement="dB",
                    capabilities={"state_class": SensorStateClass.MEASUREMENT},
                ),
            ],
        ),
    )
