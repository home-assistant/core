"""Test against characteristics captured from a SIMPLEconnect Fan.

https://github.com/home-assistant/core/issues/26180
"""
from homeassistant.components.fan import FanEntityFeature
from homeassistant.core import HomeAssistant

from ..common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_simpleconnect_fan_setup(hass: HomeAssistant) -> None:
    """Test that a SIMPLEconnect fan can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "simpleconnect_fan.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="SIMPLEconnect Fan-06F674",
            model="SIMPLEconnect",
            manufacturer="Hunter Fan",
            sw_version="",
            hw_version="",
            serial_number="1234567890abcd",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="fan.simpleconnect_fan_06f674_hunter_fan",
                    friendly_name="SIMPLEconnect Fan-06F674 Hunter Fan",
                    unique_id="00:00:00:00:00:00_1_8",
                    supported_features=FanEntityFeature.DIRECTION
                    | FanEntityFeature.SET_SPEED,
                    capabilities={
                        "preset_modes": None,
                    },
                    state="off",
                ),
            ],
        ),
    )
