"""Test against characteristics captured from a ryse smart bridge platforms."""

from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_ryse_smart_bridge_setup(hass):
    """Test that a Ryse smart bridge can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "ryse_smart_bridge.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)

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

    device_registry = dr.async_get(hass)

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
