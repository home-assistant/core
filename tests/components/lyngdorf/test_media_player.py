"""Tests for the Lyngdorf media player platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.lyngdorf.const import DOMAIN
from homeassistant.components.lyngdorf.media_player import (
    LyngdorfMainDevice,
    LyngdorfZoneBDevice,
)
from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo

from tests.common import MockConfigEntry


async def test_entities_created(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that both main zone and zone B entities are created."""
    assert init_integration.state is ConfigEntryState.LOADED

    # Check main zone entity exists
    main_zone = hass.states.get("media_player.mock_lyngdorf_main_zone")
    assert main_zone is not None
    assert main_zone.attributes["friendly_name"] == "Mock Lyngdorf Main zone"

    # Check zone B entity exists
    zone_b = hass.states.get("media_player.mock_lyngdorf_zone_b")
    assert zone_b is not None
    assert zone_b.attributes["friendly_name"] == "Mock Lyngdorf Zone B"


async def test_entity_unique_ids(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test that entity unique IDs are set correctly."""
    entity_registry = er.async_get(hass)

    # Main zone unique ID
    main_zone = entity_registry.async_get("media_player.mock_lyngdorf_main_zone")
    assert main_zone is not None
    assert main_zone.unique_id == f"{init_integration.unique_id}_main_zone"

    # Zone B unique ID
    zone_b = entity_registry.async_get("media_player.mock_lyngdorf_zone_b")
    assert zone_b is not None
    assert zone_b.unique_id == f"{init_integration.unique_id}_zone_b"


async def test_main_zone_turn_on(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test turning on main zone."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "media_player.mock_lyngdorf_main_zone"},
        blocking=True,
    )

    assert mock_receiver.power_on is True


async def test_main_zone_turn_off(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test turning off main zone."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "media_player.mock_lyngdorf_main_zone"},
        blocking=True,
    )

    assert mock_receiver.power_on is False


async def test_zone_b_turn_on(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test turning on zone B."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "media_player.mock_lyngdorf_zone_b"},
        blocking=True,
    )

    assert mock_receiver.zone_b_power_on is True


async def test_zone_b_turn_off(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test turning off zone B."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "media_player.mock_lyngdorf_zone_b"},
        blocking=True,
    )

    assert mock_receiver.zone_b_power_on is False


async def test_main_zone_volume_set(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test setting main zone volume."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {
            ATTR_ENTITY_ID: "media_player.mock_lyngdorf_main_zone",
            "volume_level": 0.5,
        },
        blocking=True,
    )

    # 0.5 * 98 - 80 = -31.0
    assert mock_receiver.volume == -31.0


async def test_zone_b_volume_set(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test setting zone B volume."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {
            ATTR_ENTITY_ID: "media_player.mock_lyngdorf_zone_b",
            "volume_level": 0.3,
        },
        blocking=True,
    )

    # 0.3 * 98 - 80 = -50.6
    assert mock_receiver.zone_b_volume == pytest.approx(-50.6)


async def test_main_zone_volume_up(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test volume up for main zone."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: "media_player.mock_lyngdorf_main_zone"},
        blocking=True,
    )

    mock_receiver.volume_up.assert_called_once()


async def test_main_zone_volume_down(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test volume down for main zone."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: "media_player.mock_lyngdorf_main_zone"},
        blocking=True,
    )

    mock_receiver.volume_down.assert_called_once()


async def test_zone_b_volume_up(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test volume up for zone B."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: "media_player.mock_lyngdorf_zone_b"},
        blocking=True,
    )

    mock_receiver.zone_b_volume_up.assert_called_once()


async def test_zone_b_volume_down(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test volume down for zone B."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: "media_player.mock_lyngdorf_zone_b"},
        blocking=True,
    )

    mock_receiver.zone_b_volume_down.assert_called_once()


async def test_main_zone_mute(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test muting main zone."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {
            ATTR_ENTITY_ID: "media_player.mock_lyngdorf_main_zone",
            "is_volume_muted": True,
        },
        blocking=True,
    )

    assert mock_receiver.mute_enabled is True


async def test_zone_b_mute(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test muting zone B."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {
            ATTR_ENTITY_ID: "media_player.mock_lyngdorf_zone_b",
            "is_volume_muted": True,
        },
        blocking=True,
    )

    assert mock_receiver.zone_b_mute_enabled is True


async def test_availability(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test availability when device disconnects and reconnects."""
    main_zone_entity_id = "media_player.mock_lyngdorf_main_zone"
    zone_b_entity_id = "media_player.mock_lyngdorf_zone_b"

    # Get all registered callbacks
    callbacks = [
        call.args[0]
        for call in mock_receiver.register_notification_callback.call_args_list
    ]
    assert len(callbacks) > 0

    mock_receiver.connected = False
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()

    main_state = hass.states.get(main_zone_entity_id)
    zone_b_state = hass.states.get(zone_b_entity_id)
    assert main_state is not None
    assert zone_b_state is not None
    assert main_state.state == "unavailable"
    assert zone_b_state.state == "unavailable"

    mock_receiver.connected = True
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()

    main_state = hass.states.get(main_zone_entity_id)
    zone_b_state = hass.states.get(zone_b_entity_id)
    assert main_state is not None
    assert zone_b_state is not None
    assert main_state.state != "unavailable"
    assert zone_b_state.state != "unavailable"


async def test_service_selects(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test selecting source and sound mode services."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {
            ATTR_ENTITY_ID: "media_player.mock_lyngdorf_main_zone",
            "source": "HDMI",
        },
        blocking=True,
    )
    assert mock_receiver.source == "HDMI"

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        {
            ATTR_ENTITY_ID: "media_player.mock_lyngdorf_main_zone",
            "sound_mode": "Movie",
        },
        blocking=True,
    )
    assert mock_receiver.sound_mode == "Movie"


def test_entity_properties(mock_receiver: MagicMock) -> None:
    """Test entity properties without hass."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123456",
        data={"host": "127.0.0.1", "model": "MP-60"},
    )
    device_info = DeviceInfo(identifiers={(DOMAIN, "device")})

    mock_receiver.power_on = True
    mock_receiver.audio_information = "Stereo"
    mock_receiver.video_information = "No video"
    mock_receiver.volume = None
    mock_receiver.available_sources = ["HDMI"]
    mock_receiver.available_sound_modes = ["Movie"]
    mock_receiver.source = "HDMI"
    mock_receiver.sound_mode = "Movie"

    main = LyngdorfMainDevice(mock_receiver, config_entry, device_info)
    assert main.state is MediaPlayerState.PLAYING
    assert main.media_title == "audio: Stereo"
    assert main.media_content_type is MediaType.MUSIC
    assert main.source_list == ["HDMI"]
    assert main.sound_mode_list == ["Movie"]
    assert main.is_volume_muted is mock_receiver.mute_enabled
    assert main.volume_level is None

    mock_receiver.video_information = "Video"
    assert main.media_title == "audio: Stereo video: Video"
    assert main.media_content_type is MediaType.VIDEO

    mock_receiver.zone_b_power_on = True
    mock_receiver.zone_b_volume = "invalid"
    zone_b = LyngdorfZoneBDevice(mock_receiver, config_entry, device_info)
    assert zone_b.state is MediaPlayerState.ON
    assert zone_b.volume_level is None


async def test_volume_clamps(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test volume level clamps at max."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {
            ATTR_ENTITY_ID: "media_player.mock_lyngdorf_main_zone",
            "volume_level": 1.0,
        },
        blocking=True,
    )

    assert mock_receiver.volume == 18.0
