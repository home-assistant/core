"""Make sure that existing Koogeek P1EU support isn't broken."""

from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_koogeek_p1eu_setup(hass):
    """Test that a Koogeek P1EU can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "koogeek_p1eu.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    # Check that the switch entity is handled correctly

    entry = entity_registry.async_get("switch.koogeek_p1_a00aa0")
    assert entry.unique_id == "homekit-EUCP03190xxxxx48-7"

    helper = Helper(
        hass, "switch.koogeek_p1_a00aa0", pairing, accessories[0], config_entry
    )
    state = await helper.poll_and_get_state()
    assert state.attributes["friendly_name"] == "Koogeek-P1-A00AA0"

    device = device_registry.async_get(entry.device_id)
    assert device.manufacturer == "Koogeek"
    assert device.name == "Koogeek-P1-A00AA0"
    assert device.model == "P1EU"
    assert device.sw_version == "2.3.7"
    assert device.via_device_id is None

    # Assert the power sensor is detected
    entry = entity_registry.async_get("sensor.koogeek_p1_a00aa0_real_time_energy")
    assert entry.unique_id == "homekit-EUCP03190xxxxx48-aid:1-sid:21-cid:21"

    helper = Helper(
        hass,
        "sensor.koogeek_p1_a00aa0_real_time_energy",
        pairing,
        accessories[0],
        config_entry,
    )
    state = await helper.poll_and_get_state()
    assert state.attributes["friendly_name"] == "Koogeek-P1-A00AA0 - Real Time Energy"

    # The sensor and switch should be part of the same device
    assert entry.device_id == device.id
