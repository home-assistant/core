"""Regression tests for Netamo Doorbell.

https://github.com/home-assistant/core/issues/44596
"""
from homeassistant.core import HomeAssistant

from ..common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    DeviceTriggerInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_netamo_doorbell_setup(hass: HomeAssistant) -> None:
    """Test that a Netamo Doorbell can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "netamo_doorbell.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Netatmo-Doorbell-g738658",
            model="Netatmo Doorbell",
            manufacturer="Netatmo",
            sw_version="80.0.0",
            hw_version="",
            serial_number="g738658",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="camera.netatmo_doorbell_g738658",
                    friendly_name="Netatmo-Doorbell-g738658",
                    unique_id="00:00:00:00:00:00_1",
                    state="idle",
                ),
            ],
            stateless_triggers=[
                DeviceTriggerInfo(type="doorbell", subtype="single_press"),
                DeviceTriggerInfo(type="doorbell", subtype="double_press"),
                DeviceTriggerInfo(type="doorbell", subtype="long_press"),
            ],
        ),
    )
