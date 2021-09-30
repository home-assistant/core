"""Make sure that Mysa Living is enumerated properly."""

from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_mysa_living_setup(hass):
    """Test that the accessory can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "mysa_living.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    # Check that the switch entity is handled correctly

    entry = entity_registry.async_get("sensor.mysa_85dda9_current_humidity")
    assert entry.unique_id == "homekit-AAAAAAA000-aid:1-sid:20-cid:27"

    helper = Helper(
        hass,
        "sensor.mysa_85dda9_current_humidity",
        pairing,
        accessories[0],
        config_entry,
    )
    state = await helper.poll_and_get_state()
    assert state.attributes["friendly_name"] == "Mysa-85dda9 - Current Humidity"

    device = device_registry.async_get(entry.device_id)
    assert device.manufacturer == "Empowered Homes Inc."
    assert device.name == "Mysa-85dda9"
    assert device.model == "v1"
    assert device.sw_version == "2.8.1"
    assert device.via_device_id is None

    # Assert the humidifier is detected
    entry = entity_registry.async_get("sensor.mysa_85dda9_current_temperature")
    assert entry.unique_id == "homekit-AAAAAAA000-aid:1-sid:20-cid:25"

    helper = Helper(
        hass,
        "sensor.mysa_85dda9_current_temperature",
        pairing,
        accessories[0],
        config_entry,
    )
    state = await helper.poll_and_get_state()
    assert state.attributes["friendly_name"] == "Mysa-85dda9 - Current Temperature"

    # The sensor should be part of the same device
    assert entry.device_id == device.id

    # Assert the light is detected
    entry = entity_registry.async_get("light.mysa_85dda9")
    assert entry.unique_id == "homekit-AAAAAAA000-40"

    helper = Helper(
        hass,
        "light.mysa_85dda9",
        pairing,
        accessories[0],
        config_entry,
    )
    state = await helper.poll_and_get_state()
    assert state.attributes["friendly_name"] == "Mysa-85dda9"

    # The light should be part of the same device
    assert entry.device_id == device.id

    # Assert the climate entity is detected
    entry = entity_registry.async_get("climate.mysa_85dda9")
    assert entry.unique_id == "homekit-AAAAAAA000-20"

    helper = Helper(
        hass,
        "climate.mysa_85dda9",
        pairing,
        accessories[0],
        config_entry,
    )
    state = await helper.poll_and_get_state()
    assert state.attributes["friendly_name"] == "Mysa-85dda9"

    # The light should be part of the same device
    assert entry.device_id == device.id
