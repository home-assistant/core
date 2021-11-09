"""
Make sure that existing Koogeek SW2 is enumerated correctly.

This Koogeek device has a custom power sensor that extra handling.

It should have 2 entities - the actual switch and a sensor for power usage.
"""

from homeassistant.const import POWER_WATT
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_koogeek_ls1_setup(hass):
    """Test that a Koogeek LS1 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "koogeek_sw2.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)

    # Assert that the switch entity is correctly added to the entity registry
    entry = entity_registry.async_get("switch.koogeek_sw2_187a91")
    assert entry.unique_id == "homekit-CNNT061751001372-8"

    helper = Helper(
        hass, "switch.koogeek_sw2_187a91", pairing, accessories[0], config_entry
    )
    state = await helper.poll_and_get_state()

    # Assert that the friendly name is detected correctly
    assert state.attributes["friendly_name"] == "Koogeek-SW2-187A91"

    device_registry = dr.async_get(hass)

    device = device_registry.async_get(entry.device_id)
    assert device.manufacturer == "Koogeek"
    assert device.name == "Koogeek-SW2-187A91"
    assert device.model == "KH02CN"
    assert device.sw_version == "1.0.3"
    assert device.via_device_id is None

    # Assert that the power sensor entity is correctly added to the entity registry
    entry = entity_registry.async_get("sensor.koogeek_sw2_187a91_real_time_energy")
    assert entry.unique_id == "homekit-CNNT061751001372-aid:1-sid:14-cid:18"

    helper = Helper(
        hass,
        "sensor.koogeek_sw2_187a91_real_time_energy",
        pairing,
        accessories[0],
        config_entry,
    )
    state = await helper.poll_and_get_state()

    # Assert that the friendly name is detected correctly
    assert state.attributes["friendly_name"] == "Koogeek-SW2-187A91 - Real Time Energy"
    assert state.attributes["unit_of_measurement"] == POWER_WATT

    device_registry = dr.async_get(hass)

    assert device.id == entry.device_id
