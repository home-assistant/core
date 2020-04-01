"""Tests for handling accessories on a Hue bridge via HomeKit."""

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_hue_bridge_setup(hass):
    """Test that a Hue hub can be correctly setup in HA via HomeKit."""
    accessories = await setup_accessories_from_file(hass, "hue_bridge.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # Check that the battery is correctly found and set up
    battery_id = "sensor.hue_dimmer_switch_battery"
    battery = entity_registry.async_get(battery_id)
    assert battery.unique_id == "homekit-6623462389072572-644245094400"

    battery_helper = Helper(
        hass, "sensor.hue_dimmer_switch_battery", pairing, accessories[0], config_entry
    )
    battery_state = await battery_helper.poll_and_get_state()
    assert battery_state.attributes["friendly_name"] == "Hue dimmer switch Battery"
    assert battery_state.attributes["icon"] == "mdi:battery"
    assert battery_state.state == "100"

    device_registry = await hass.helpers.device_registry.async_get_registry()

    device = device_registry.async_get(battery.device_id)
    assert device.manufacturer == "Philips"
    assert device.name == "Hue dimmer switch"
    assert device.model == "RWL021"
    assert device.sw_version == "45.1.17846"
