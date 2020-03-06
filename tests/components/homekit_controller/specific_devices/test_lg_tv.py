"""Make sure that handling real world LG HomeKit characteristics isn't broken."""


from homeassistant.components.media_player.const import SUPPORT_PAUSE, SUPPORT_PLAY

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_lg_tv(hass):
    """Test that a Koogeek LS1 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "lg_tv.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # Assert that the entity is correctly added to the entity registry
    entry = entity_registry.async_get("media_player.lg_webos_tv_af80")
    assert entry.unique_id == "homekit-999AAAAAA999-48"

    helper = Helper(
        hass, "media_player.lg_webos_tv_af80", pairing, accessories[0], config_entry
    )
    state = await helper.poll_and_get_state()

    # Assert that the friendly name is detected correctly
    assert state.attributes["friendly_name"] == "LG webOS TV AF80"

    # Assert that all optional features the LS1 supports are detected
    assert state.attributes["supported_features"] == (SUPPORT_PAUSE | SUPPORT_PLAY)

    device_registry = await hass.helpers.device_registry.async_get_registry()

    device = device_registry.async_get(entry.device_id)
    assert device.manufacturer == "LG Electronics"
    assert device.name == "LG webOS TV AF80"
    assert device.model == "OLED55B9PUA"
    assert device.sw_version == "04.71.04"
    assert device.via_device_id is None
