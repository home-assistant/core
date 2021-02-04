"""Test against characteristics captured from the Home Assistant HomeKit bridge running demo platforms."""

from homeassistant.components.fan import (
    SUPPORT_DIRECTION,
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED,
)

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_homeassistant_bridge_fan_setup(hass):
    """Test that a SIMPLEconnect fan can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(
        hass, "home_assistant_bridge_fan.json"
    )
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # Check that the fan is correctly found and set up
    fan_id = "fan.living_room_fan"
    fan = entity_registry.async_get(fan_id)
    assert fan.unique_id == "homekit-fan.living_room_fan-8"

    fan_helper = Helper(
        hass,
        "fan.living_room_fan",
        pairing,
        accessories[0],
        config_entry,
    )

    fan_state = await fan_helper.poll_and_get_state()
    assert fan_state.attributes["friendly_name"] == "Living Room Fan"
    assert fan_state.state == "off"
    assert fan_state.attributes["supported_features"] == (
        SUPPORT_DIRECTION | SUPPORT_SET_SPEED | SUPPORT_OSCILLATE
    )

    device_registry = await hass.helpers.device_registry.async_get_registry()

    device = device_registry.async_get(fan.device_id)
    assert device.manufacturer == "Home Assistant"
    assert device.name == "Living Room Fan"
    assert device.model == "Fan"
    assert device.sw_version == "0.104.0.dev0"

    bridge = device = device_registry.async_get(device.via_device_id)
    assert bridge.manufacturer == "Home Assistant"
    assert bridge.name == "Home Assistant Bridge"
    assert bridge.model == "Bridge"
    assert bridge.sw_version == "0.104.0.dev0"
