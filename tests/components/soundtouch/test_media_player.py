"""Test the SoundTouch component."""
from datetime import timedelta
from typing import Any

from requests_mock import Mocker

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.components.soundtouch.const import (
    DOMAIN,
    SERVICE_ADD_ZONE_SLAVE,
    SERVICE_CREATE_ZONE,
    SERVICE_PLAY_EVERYWHERE,
    SERVICE_REMOVE_ZONE_SLAVE,
)
from homeassistant.components.soundtouch.media_player import (
    ATTR_SOUNDTOUCH_GROUP,
    ATTR_SOUNDTOUCH_ZONE,
)
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import STATE_OFF, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import DEVICE_1_ENTITY_ID, DEVICE_2_ENTITY_ID

from tests.common import MockConfigEntry, async_fire_time_changed


async def setup_soundtouch(hass: HomeAssistant, *mock_entries: MockConfigEntry):
    """Initialize media_player for tests."""
    assert await async_setup_component(hass, MEDIA_PLAYER_DOMAIN, {})

    for mock_entry in mock_entries:
        mock_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()


async def _test_key_service(
    hass: HomeAssistant,
    requests_mock_key,
    service: str,
    service_data: dict[str, Any],
    key_name: str,
):
    """Test API calls that use the /key endpoint to emulate physical button clicks."""
    requests_mock_key.reset()
    await hass.services.async_call("media_player", service, service_data, True)
    assert requests_mock_key.call_count == 2
    assert f">{key_name}</key>" in requests_mock_key.last_request.text


async def test_playing_media(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_upnp,
) -> None:
    """Test playing media info."""
    await setup_soundtouch(hass, device1_config)

    entity_state = hass.states.get(DEVICE_1_ENTITY_ID)
    assert entity_state.state == STATE_PLAYING
    assert entity_state.attributes[ATTR_MEDIA_TITLE] == "MockArtist - MockTrack"
    assert entity_state.attributes[ATTR_MEDIA_TRACK] == "MockTrack"
    assert entity_state.attributes[ATTR_MEDIA_ARTIST] == "MockArtist"
    assert entity_state.attributes[ATTR_MEDIA_ALBUM_NAME] == "MockAlbum"
    assert entity_state.attributes[ATTR_MEDIA_DURATION] == 42


async def test_playing_radio(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_radio,
) -> None:
    """Test playing radio info."""
    await setup_soundtouch(hass, device1_config)

    entity_state = hass.states.get(DEVICE_1_ENTITY_ID)
    assert entity_state.state == STATE_PLAYING
    assert entity_state.attributes[ATTR_MEDIA_TITLE] == "MockStation"


async def test_playing_aux(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_aux,
) -> None:
    """Test playing AUX info."""
    await setup_soundtouch(hass, device1_config)

    entity_state = hass.states.get(DEVICE_1_ENTITY_ID)
    assert entity_state.state == STATE_PLAYING
    assert entity_state.attributes[ATTR_INPUT_SOURCE] == "AUX"


async def test_playing_bluetooth(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_bluetooth,
) -> None:
    """Test playing Bluetooth info."""
    await setup_soundtouch(hass, device1_config)

    entity_state = hass.states.get(DEVICE_1_ENTITY_ID)
    assert entity_state.state == STATE_PLAYING
    assert entity_state.attributes[ATTR_INPUT_SOURCE] == "BLUETOOTH"
    assert entity_state.attributes[ATTR_MEDIA_TRACK] == "MockTrack"
    assert entity_state.attributes[ATTR_MEDIA_ARTIST] == "MockArtist"
    assert entity_state.attributes[ATTR_MEDIA_ALBUM_NAME] == "MockAlbum"


async def test_get_volume_level(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_upnp,
) -> None:
    """Test volume level."""
    await setup_soundtouch(hass, device1_config)

    entity_state = hass.states.get(DEVICE_1_ENTITY_ID)
    assert entity_state.attributes["volume_level"] == 0.12


async def test_get_state_off(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_standby,
) -> None:
    """Test state device is off."""
    await setup_soundtouch(hass, device1_config)

    entity_state = hass.states.get(DEVICE_1_ENTITY_ID)
    assert entity_state.state == STATE_OFF


async def test_get_state_pause(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_upnp_paused,
) -> None:
    """Test state device is paused."""
    await setup_soundtouch(hass, device1_config)

    entity_state = hass.states.get(DEVICE_1_ENTITY_ID)
    assert entity_state.state == STATE_PAUSED


async def test_is_muted(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_upnp,
    device1_volume_muted: str,
) -> None:
    """Test device volume is muted."""
    with Mocker(real_http=True) as mocker:
        mocker.get("/volume", text=device1_volume_muted)

        await setup_soundtouch(hass, device1_config)

        entity_state = hass.states.get(DEVICE_1_ENTITY_ID)
        assert entity_state.attributes[ATTR_MEDIA_VOLUME_MUTED]


async def test_should_turn_off(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_upnp,
    device1_requests_mock_key,
) -> None:
    """Test device is turned off."""
    await setup_soundtouch(hass, device1_config)
    await _test_key_service(
        hass,
        device1_requests_mock_key,
        "turn_off",
        {"entity_id": DEVICE_1_ENTITY_ID},
        "POWER",
    )


async def test_should_turn_on(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_standby,
    device1_requests_mock_key,
) -> None:
    """Test device is turned on."""
    await setup_soundtouch(hass, device1_config)
    await _test_key_service(
        hass,
        device1_requests_mock_key,
        "turn_on",
        {"entity_id": DEVICE_1_ENTITY_ID},
        "POWER",
    )


async def test_volume_up(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_upnp,
    device1_requests_mock_key,
) -> None:
    """Test volume up."""
    await setup_soundtouch(hass, device1_config)
    await _test_key_service(
        hass,
        device1_requests_mock_key,
        "volume_up",
        {"entity_id": DEVICE_1_ENTITY_ID},
        "VOLUME_UP",
    )


async def test_volume_down(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_upnp,
    device1_requests_mock_key,
) -> None:
    """Test volume down."""
    await setup_soundtouch(hass, device1_config)
    await _test_key_service(
        hass,
        device1_requests_mock_key,
        "volume_down",
        {"entity_id": DEVICE_1_ENTITY_ID},
        "VOLUME_DOWN",
    )


async def test_set_volume_level(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_upnp,
    device1_requests_mock_volume,
) -> None:
    """Test set volume level."""
    await setup_soundtouch(hass, device1_config)

    assert device1_requests_mock_volume.call_count == 0
    await hass.services.async_call(
        "media_player",
        "volume_set",
        {"entity_id": DEVICE_1_ENTITY_ID, "volume_level": 0.17},
        True,
    )
    assert device1_requests_mock_volume.call_count == 1
    assert "<volume>17</volume>" in device1_requests_mock_volume.last_request.text


async def test_mute(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_upnp,
    device1_requests_mock_key,
) -> None:
    """Test mute volume."""
    await setup_soundtouch(hass, device1_config)
    await _test_key_service(
        hass,
        device1_requests_mock_key,
        "volume_mute",
        {"entity_id": DEVICE_1_ENTITY_ID, "is_volume_muted": True},
        "MUTE",
    )


async def test_play(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_upnp_paused,
    device1_requests_mock_key,
) -> None:
    """Test play command."""
    await setup_soundtouch(hass, device1_config)
    await _test_key_service(
        hass,
        device1_requests_mock_key,
        "media_play",
        {"entity_id": DEVICE_1_ENTITY_ID},
        "PLAY",
    )


async def test_pause(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_upnp,
    device1_requests_mock_key,
) -> None:
    """Test pause command."""
    await setup_soundtouch(hass, device1_config)
    await _test_key_service(
        hass,
        device1_requests_mock_key,
        "media_pause",
        {"entity_id": DEVICE_1_ENTITY_ID},
        "PAUSE",
    )


async def test_play_pause(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_upnp,
    device1_requests_mock_key,
) -> None:
    """Test play/pause."""
    await setup_soundtouch(hass, device1_config)
    await _test_key_service(
        hass,
        device1_requests_mock_key,
        "media_play_pause",
        {"entity_id": DEVICE_1_ENTITY_ID},
        "PLAY_PAUSE",
    )


async def test_next_previous_track(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_upnp,
    device1_requests_mock_key,
) -> None:
    """Test next/previous track."""
    await setup_soundtouch(hass, device1_config)
    await _test_key_service(
        hass,
        device1_requests_mock_key,
        "media_next_track",
        {"entity_id": DEVICE_1_ENTITY_ID},
        "NEXT_TRACK",
    )

    await _test_key_service(
        hass,
        device1_requests_mock_key,
        "media_previous_track",
        {"entity_id": DEVICE_1_ENTITY_ID},
        "PREV_TRACK",
    )


async def test_play_media(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_standby,
    device1_requests_mock_select,
) -> None:
    """Test play preset 1."""
    await setup_soundtouch(hass, device1_config)

    assert device1_requests_mock_select.call_count == 0
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            "entity_id": DEVICE_1_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: "PLAYLIST",
            ATTR_MEDIA_CONTENT_ID: 1,
        },
        True,
    )
    assert device1_requests_mock_select.call_count == 1
    assert (
        'location="http://homeassistant:8123/media/local/test.mp3"'
        in device1_requests_mock_select.last_request.text
    )

    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            "entity_id": DEVICE_1_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: "PLAYLIST",
            ATTR_MEDIA_CONTENT_ID: 2,
        },
        True,
    )
    assert device1_requests_mock_select.call_count == 2
    assert "MockStation" in device1_requests_mock_select.last_request.text


async def test_play_media_url(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_standby,
    device1_requests_mock_dlna,
) -> None:
    """Test play preset 1."""
    await setup_soundtouch(hass, device1_config)

    assert device1_requests_mock_dlna.call_count == 0
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            "entity_id": DEVICE_1_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: "MUSIC",
            ATTR_MEDIA_CONTENT_ID: "http://fqdn/file.mp3",
        },
        True,
    )
    assert device1_requests_mock_dlna.call_count == 1
    assert "http://fqdn/file.mp3" in device1_requests_mock_dlna.last_request.text


async def test_select_source_aux(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_standby,
    device1_requests_mock_select,
) -> None:
    """Test select AUX."""
    await setup_soundtouch(hass, device1_config)

    assert device1_requests_mock_select.call_count == 0
    await hass.services.async_call(
        "media_player",
        "select_source",
        {"entity_id": DEVICE_1_ENTITY_ID, ATTR_INPUT_SOURCE: "AUX"},
        True,
    )
    assert device1_requests_mock_select.call_count == 1
    assert "AUX" in device1_requests_mock_select.last_request.text


async def test_select_source_bluetooth(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_standby,
    device1_requests_mock_select,
) -> None:
    """Test select Bluetooth."""
    await setup_soundtouch(hass, device1_config)

    assert device1_requests_mock_select.call_count == 0
    await hass.services.async_call(
        "media_player",
        "select_source",
        {"entity_id": DEVICE_1_ENTITY_ID, ATTR_INPUT_SOURCE: "BLUETOOTH"},
        True,
    )
    assert device1_requests_mock_select.call_count == 1
    assert "BLUETOOTH" in device1_requests_mock_select.last_request.text


async def test_select_source_invalid_source(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device1_requests_mock_standby,
    device1_requests_mock_select,
) -> None:
    """Test select unsupported source."""
    await setup_soundtouch(hass, device1_config)

    assert not device1_requests_mock_select.called
    await hass.services.async_call(
        "media_player",
        "select_source",
        {
            "entity_id": DEVICE_1_ENTITY_ID,
            ATTR_INPUT_SOURCE: "SOMETHING_UNSUPPORTED",
        },
        True,
    )
    assert not device1_requests_mock_select.called


async def test_play_everywhere(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device2_config: MockConfigEntry,
    device1_requests_mock_standby,
    device2_requests_mock_standby,
    device1_requests_mock_set_zone,
) -> None:
    """Test play everywhere."""
    await setup_soundtouch(hass, device1_config)

    # no slaves, set zone must not be called
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_EVERYWHERE,
        {"master": DEVICE_1_ENTITY_ID},
        True,
    )
    assert device1_requests_mock_set_zone.call_count == 0

    await setup_soundtouch(hass, device2_config)

    # one master, one slave => set zone
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_EVERYWHERE,
        {"master": DEVICE_1_ENTITY_ID},
        True,
    )
    assert device1_requests_mock_set_zone.call_count == 1

    # unknown master, set zone must not be called
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_EVERYWHERE,
        {"master": "media_player.entity_X"},
        True,
    )
    assert device1_requests_mock_set_zone.call_count == 1


async def test_create_zone(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device2_config: MockConfigEntry,
    device1_requests_mock_standby,
    device2_requests_mock_standby,
    device1_requests_mock_set_zone,
) -> None:
    """Test creating a zone."""
    await setup_soundtouch(hass, device1_config, device2_config)

    assert device1_requests_mock_set_zone.call_count == 0

    # one master, one slave => set zone
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_ZONE,
        {
            "master": DEVICE_1_ENTITY_ID,
            "slaves": [DEVICE_2_ENTITY_ID],
        },
        True,
    )
    assert device1_requests_mock_set_zone.call_count == 1

    # unknown master, set zone must not be called
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_ZONE,
        {"master": "media_player.entity_X", "slaves": [DEVICE_2_ENTITY_ID]},
        True,
    )
    assert device1_requests_mock_set_zone.call_count == 1

    # no slaves, set zone must not be called
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_ZONE,
        {"master": DEVICE_1_ENTITY_ID, "slaves": []},
        True,
    )
    assert device1_requests_mock_set_zone.call_count == 1


async def test_remove_zone_slave(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device2_config: MockConfigEntry,
    device1_requests_mock_standby,
    device2_requests_mock_standby,
    device1_requests_mock_remove_zone_slave,
) -> None:
    """Test removing a slave from an existing zone."""
    await setup_soundtouch(hass, device1_config, device2_config)

    # remove one slave
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ZONE_SLAVE,
        {
            "master": DEVICE_1_ENTITY_ID,
            "slaves": [DEVICE_2_ENTITY_ID],
        },
        True,
    )
    assert device1_requests_mock_remove_zone_slave.call_count == 1

    # unknown master, remove zone slave is not called
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ZONE_SLAVE,
        {"master": "media_player.entity_X", "slaves": [DEVICE_2_ENTITY_ID]},
        True,
    )
    assert device1_requests_mock_remove_zone_slave.call_count == 1

    # no slave to remove, remove zone slave is not called
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ZONE_SLAVE,
        {"master": DEVICE_1_ENTITY_ID, "slaves": []},
        True,
    )
    assert device1_requests_mock_remove_zone_slave.call_count == 1


async def test_add_zone_slave(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device2_config: MockConfigEntry,
    device1_requests_mock_standby,
    device2_requests_mock_standby,
    device1_requests_mock_add_zone_slave,
) -> None:
    """Test adding a slave to a zone."""
    await setup_soundtouch(hass, device1_config, device2_config)

    # add one slave
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_ZONE_SLAVE,
        {
            "master": DEVICE_1_ENTITY_ID,
            "slaves": [DEVICE_2_ENTITY_ID],
        },
        True,
    )
    assert device1_requests_mock_add_zone_slave.call_count == 1

    # unknown master, add zone slave is not called
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_ZONE_SLAVE,
        {"master": "media_player.entity_X", "slaves": [DEVICE_2_ENTITY_ID]},
        True,
    )
    assert device1_requests_mock_add_zone_slave.call_count == 1

    # no slave to add, add zone slave is not called
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_ZONE_SLAVE,
        {"master": DEVICE_1_ENTITY_ID, "slaves": ["media_player.entity_X"]},
        True,
    )
    assert device1_requests_mock_add_zone_slave.call_count == 1


async def test_zone_attributes(
    hass: HomeAssistant,
    device1_config: MockConfigEntry,
    device2_config: MockConfigEntry,
    device1_requests_mock_standby,
    device2_requests_mock_standby,
) -> None:
    """Test zone attributes."""
    await setup_soundtouch(hass, device1_config, device2_config)

    # Fast-forward time to allow all entities to be set up and updated again
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    entity_1_state = hass.states.get(DEVICE_1_ENTITY_ID)
    assert entity_1_state.attributes[ATTR_SOUNDTOUCH_ZONE]["is_master"]
    assert (
        entity_1_state.attributes[ATTR_SOUNDTOUCH_ZONE]["master"] == DEVICE_1_ENTITY_ID
    )
    assert entity_1_state.attributes[ATTR_SOUNDTOUCH_ZONE]["slaves"] == [
        DEVICE_2_ENTITY_ID
    ]
    assert entity_1_state.attributes[ATTR_SOUNDTOUCH_GROUP] == [
        DEVICE_1_ENTITY_ID,
        DEVICE_2_ENTITY_ID,
    ]

    entity_2_state = hass.states.get(DEVICE_2_ENTITY_ID)
    assert not entity_2_state.attributes[ATTR_SOUNDTOUCH_ZONE]["is_master"]
    assert (
        entity_2_state.attributes[ATTR_SOUNDTOUCH_ZONE]["master"] == DEVICE_1_ENTITY_ID
    )
    assert entity_2_state.attributes[ATTR_SOUNDTOUCH_ZONE]["slaves"] == [
        DEVICE_2_ENTITY_ID
    ]
    assert entity_2_state.attributes[ATTR_SOUNDTOUCH_GROUP] == [
        DEVICE_1_ENTITY_ID,
        DEVICE_2_ENTITY_ID,
    ]
