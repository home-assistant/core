"""Test against characteristics captured from the Home Assistant HomeKit bridge running demo platforms."""

from homeassistant.components.fan import (
    SUPPORT_DIRECTION,
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED,
)

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_homeassistant_bridge_fan_setup(hass):
    """Test that a SIMPLEconnect fan can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(
        hass, "home_assistant_bridge_fan.json"
    )
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="Home Assistant Bridge",
            model="Bridge",
            manufacturer="Home Assistant",
            sw_version="0.104.0.dev0",
            hw_version="",
            serial_number="homekit.bridge",
            devices=[
                DeviceTestInfo(
                    name="Living Room Fan",
                    model="Fan",
                    manufacturer="Home Assistant",
                    sw_version="0.104.0.dev0",
                    hw_version="",
                    serial_number="fan.living_room_fan",
                    unique_id="00:00:00:00:00:00:aid:1256851357",
                    devices=[],
                    entities=[
                        EntityTestInfo(
                            entity_id="fan.living_room_fan",
                            friendly_name="Living Room Fan",
                            unique_id="homekit-fan.living_room_fan-8",
                            supported_features=(
                                SUPPORT_DIRECTION
                                | SUPPORT_SET_SPEED
                                | SUPPORT_OSCILLATE
                            ),
                            capabilities={
                                "preset_modes": None,
                            },
                            state="off",
                        )
                    ],
                ),
            ],
            entities=[],
        ),
    )
