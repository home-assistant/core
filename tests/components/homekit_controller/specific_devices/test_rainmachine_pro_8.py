"""
Make sure that existing RainMachine support isn't broken.

https://github.com/home-assistant/core/issues/31745
"""

from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_rainmachine_pro_8_setup(hass):
    """Test that a RainMachine can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "rainmachine-pro-8.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)

    # Assert that the entity is correctly added to the entity registry
    entry = entity_registry.async_get("switch.rainmachine_00ce4a")
    assert entry.unique_id == "homekit-00aa0000aa0a-512"

    helper = Helper(
        hass, "switch.rainmachine_00ce4a", pairing, accessories[0], config_entry
    )
    state = await helper.poll_and_get_state()

    # Assert that the friendly name is detected correctly
    assert state.attributes["friendly_name"] == "RainMachine-00ce4a"

    device_registry = dr.async_get(hass)

    device = device_registry.async_get(entry.device_id)
    assert device.manufacturer == "Green Electronics LLC"
    assert device.name == "RainMachine-00ce4a"
    assert device.model == "SPK5 Pro"
    assert device.sw_version == "1.0.4"
    assert device.via_device_id is None

    # The device is made up of multiple valves - make sure we have enumerated them all
    entry = entity_registry.async_get("switch.rainmachine_00ce4a_2")
    assert entry.unique_id == "homekit-00aa0000aa0a-768"

    entry = entity_registry.async_get("switch.rainmachine_00ce4a_3")
    assert entry.unique_id == "homekit-00aa0000aa0a-1024"

    entry = entity_registry.async_get("switch.rainmachine_00ce4a_4")
    assert entry.unique_id == "homekit-00aa0000aa0a-1280"

    entry = entity_registry.async_get("switch.rainmachine_00ce4a_5")
    assert entry.unique_id == "homekit-00aa0000aa0a-1536"

    entry = entity_registry.async_get("switch.rainmachine_00ce4a_6")
    assert entry.unique_id == "homekit-00aa0000aa0a-1792"

    entry = entity_registry.async_get("switch.rainmachine_00ce4a_7")
    assert entry.unique_id == "homekit-00aa0000aa0a-2048"

    entry = entity_registry.async_get("switch.rainmachine_00ce4a_8")
    assert entry.unique_id == "homekit-00aa0000aa0a-2304"

    entry = entity_registry.async_get("switch.rainmachine_00ce4a_9")
    assert entry is None
