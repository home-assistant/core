"""Make sure that handling real world LG HomeKit characteristics isn't broken."""

from homeassistant.components.media_player.const import (
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_SELECT_SOURCE,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import async_get_device_automations
from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_lg_tv(hass):
    """Test that a Koogeek LS1 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "lg_tv.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)

    # Assert that the entity is correctly added to the entity registry
    entry = entity_registry.async_get("media_player.lg_webos_tv_af80")
    assert entry.unique_id == "homekit-999AAAAAA999-48"

    helper = Helper(
        hass, "media_player.lg_webos_tv_af80", pairing, accessories[0], config_entry
    )
    state = await helper.poll_and_get_state()

    # Assert that the friendly name is detected correctly
    assert state.attributes["friendly_name"] == "LG webOS TV AF80"

    # Assert that all channels were found and that we know which is active.
    assert state.attributes["source_list"] == [
        "AirPlay",
        "Live TV",
        "HDMI 1",
        "Sony",
        "Apple",
        "AV",
        "HDMI 4",
    ]
    assert state.attributes["source"] == "HDMI 4"

    # Assert that all optional features the LS1 supports are detected
    assert state.attributes["supported_features"] == (
        SUPPORT_PAUSE | SUPPORT_PLAY | SUPPORT_SELECT_SOURCE
    )

    # The LG TV doesn't (at least at this patch level) report its media state via
    # CURRENT_MEDIA_STATE. Therefore "ok" is the best we can say.
    assert state.state == "ok"

    device_registry = dr.async_get(hass)

    device = device_registry.async_get(entry.device_id)
    assert device.manufacturer == "LG Electronics"
    assert device.name == "LG webOS TV AF80"
    assert device.model == "OLED55B9PUA"
    assert device.sw_version == "04.71.04"
    assert device.via_device_id is None

    # A TV has media player device triggers
    triggers = await async_get_device_automations(hass, "trigger", device.id)
    for trigger in triggers:
        assert trigger["domain"] == "media_player"
