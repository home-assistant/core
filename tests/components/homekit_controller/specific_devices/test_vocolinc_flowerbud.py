"""Make sure that Vocolinc Flowerbud is enumerated properly."""

from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_vocolinc_flowerbud_setup(hass):
    """Test that a Vocolinc Flowerbud can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "vocolinc_flowerbud.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    # Check that the switch entity is handled correctly

    entry = entity_registry.async_get("number.vocolinc_flowerbud_0d324b")
    assert entry.unique_id == "homekit-AM01121849000327-aid:1-sid:30-cid:38"

    helper = Helper(
        hass, "number.vocolinc_flowerbud_0d324b", pairing, accessories[0], config_entry
    )
    state = await helper.poll_and_get_state()
    assert state.attributes["friendly_name"] == "VOCOlinc-Flowerbud-0d324b"

    device = device_registry.async_get(entry.device_id)
    assert device.manufacturer == "VOCOlinc"
    assert device.name == "VOCOlinc-Flowerbud-0d324b"
    assert device.model == "Flowerbud"
    assert device.sw_version == "3.121.2"
    assert device.via_device_id is None

    # Assert the humidifier is detected
    entry = entity_registry.async_get("humidifier.vocolinc_flowerbud_0d324b")
    assert entry.unique_id == "homekit-AM01121849000327-30"

    helper = Helper(
        hass,
        "humidifier.vocolinc_flowerbud_0d324b",
        pairing,
        accessories[0],
        config_entry,
    )
    state = await helper.poll_and_get_state()
    assert state.attributes["friendly_name"] == "VOCOlinc-Flowerbud-0d324b"

    # The sensor and switch should be part of the same device
    assert entry.device_id == device.id

    # Assert the light is detected
    entry = entity_registry.async_get("light.vocolinc_flowerbud_0d324b")
    assert entry.unique_id == "homekit-AM01121849000327-9"

    helper = Helper(
        hass,
        "light.vocolinc_flowerbud_0d324b",
        pairing,
        accessories[0],
        config_entry,
    )
    state = await helper.poll_and_get_state()
    assert state.attributes["friendly_name"] == "VOCOlinc-Flowerbud-0d324b"

    # The sensor and switch should be part of the same device
    assert entry.device_id == device.id

    # Assert the humidity sensory is detected
    entry = entity_registry.async_get(
        "sensor.vocolinc_flowerbud_0d324b_current_humidity"
    )
    assert entry.unique_id == "homekit-AM01121849000327-aid:1-sid:30-cid:33"

    helper = Helper(
        hass,
        "sensor.vocolinc_flowerbud_0d324b_current_humidity",
        pairing,
        accessories[0],
        config_entry,
    )
    state = await helper.poll_and_get_state()
    assert (
        state.attributes["friendly_name"]
        == "VOCOlinc-Flowerbud-0d324b - Current Humidity"
    )

    # The sensor and humidifier should be part of the same device
    assert entry.device_id == device.id
