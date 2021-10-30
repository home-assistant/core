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

    # Check that the cover.master_bath_south is correctly found and set up
    cover_id = "cover.master_bath_south"
    cover = entity_registry.async_get(cover_id)
    assert cover.unique_id == "homekit-00:00:00:00:00:00-2-48"

    cover_helper = Helper(
        hass,
        cover_id,
        pairing,
        accessories[0],
        config_entry,
    )

    cover_state = await cover_helper.poll_and_get_state()
    assert cover_state.attributes["friendly_name"] == "Master Bath South"
    assert cover_state.state == "closed"

    device_registry = dr.async_get(hass)

    device = device_registry.async_get(cover.device_id)
    assert device.manufacturer == "RYSE Inc."
    assert device.name == "Master Bath South"
    assert device.model == "RYSE Shade"
    assert device.sw_version == "3.0.8"

    bridge = device_registry.async_get(device.via_device_id)
    assert bridge.manufacturer == "RYSE Inc."
    assert bridge.name == "RYSE SmartBridge"
    assert bridge.model == "RYSE SmartBridge"
    assert bridge.sw_version == "1.3.0"

    # Check that the cover.ryse_smartshade is correctly found and set up
    cover_id = "cover.ryse_smartshade"
    cover = entity_registry.async_get(cover_id)
    assert cover.unique_id == "homekit-00:00:00:00:00:00-3-48"

    cover_helper = Helper(
        hass,
        cover_id,
        pairing,
        accessories[0],
        config_entry,
    )

    cover_state = await cover_helper.poll_and_get_state()
    assert cover_state.attributes["friendly_name"] == "RYSE SmartShade"
    assert cover_state.state == "open"

    device_registry = dr.async_get(hass)

    device = device_registry.async_get(cover.device_id)
    assert device.manufacturer == "RYSE Inc."
    assert device.name == "RYSE SmartShade"
    assert device.model == "RYSE Shade"
    assert device.sw_version == ""
