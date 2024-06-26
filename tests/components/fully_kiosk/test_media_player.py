"""Test the Fully Kiosk Browser media player."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.components import media_player
from homeassistant.components.fully_kiosk.const import DOMAIN, MEDIA_SUPPORT_FULLYKIOSK
from homeassistant.components.media_source import DOMAIN as MS_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_media_player(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test standard Fully Kiosk media player."""
    state = hass.states.get("media_player.amazon_fire")
    assert state

    entry = entity_registry.async_get("media_player.amazon_fire")
    assert entry
    assert entry.unique_id == "abcdef-123456-mediaplayer"
    assert entry.supported_features == MEDIA_SUPPORT_FULLYKIOSK

    await hass.services.async_call(
        media_player.DOMAIN,
        "play_media",
        {
            ATTR_ENTITY_ID: "media_player.amazon_fire",
            "media_content_type": "music",
            "media_content_id": "test.mp3",
        },
        blocking=True,
    )
    assert len(mock_fully_kiosk.playSound.mock_calls) == 1

    with patch(
        "homeassistant.components.media_source.async_resolve_media",
        return_value=Mock(url="http://example.com/test.mp3"),
    ):
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                ATTR_ENTITY_ID: "media_player.amazon_fire",
                "media_content_id": "media-source://some_source/some_id",
                "media_content_type": "audio/mpeg",
            },
            blocking=True,
        )

        assert len(mock_fully_kiosk.playSound.mock_calls) == 2
        assert (
            mock_fully_kiosk.playSound.mock_calls[1].args[0]
            == "http://example.com/test.mp3"
        )

    await hass.services.async_call(
        media_player.DOMAIN,
        "media_stop",
        {
            ATTR_ENTITY_ID: "media_player.amazon_fire",
        },
        blocking=True,
    )
    assert len(mock_fully_kiosk.stopSound.mock_calls) == 1

    await hass.services.async_call(
        media_player.DOMAIN,
        "volume_set",
        {
            ATTR_ENTITY_ID: "media_player.amazon_fire",
            "volume_level": 0.5,
        },
        blocking=True,
    )
    assert len(mock_fully_kiosk.setAudioVolume.mock_calls) == 1

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.configuration_url == "http://192.168.1.234:2323"
    assert device_entry.entry_type is None
    assert device_entry.hw_version is None
    assert device_entry.identifiers == {(DOMAIN, "abcdef-123456")}
    assert device_entry.manufacturer == "amzn"
    assert device_entry.model == "KFDOWI"
    assert device_entry.name == "Amazon Fire"
    assert device_entry.sw_version == "1.42.5"


@pytest.mark.parametrize("media_content_type", ["video", "video/mp4"])
async def test_media_player_video(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
    media_content_type: str,
) -> None:
    """Test Fully Kiosk media player for videos."""
    await hass.services.async_call(
        media_player.DOMAIN,
        "play_media",
        {
            ATTR_ENTITY_ID: "media_player.amazon_fire",
            "media_content_type": media_content_type,
            "media_content_id": "test.mp4",
        },
        blocking=True,
    )
    assert len(mock_fully_kiosk.sendCommand.mock_calls) == 1
    mock_fully_kiosk.sendCommand.assert_called_with(
        "playVideo", url="test.mp4", stream=3, showControls=1, exitOnCompletion=1
    )

    await hass.services.async_call(
        media_player.DOMAIN,
        "media_stop",
        {
            ATTR_ENTITY_ID: "media_player.amazon_fire",
        },
        blocking=True,
    )
    mock_fully_kiosk.sendCommand.assert_called_with("stopVideo")


async def test_media_player_unsupported(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test Fully Kiosk media player for unsupported media."""
    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            media_player.DOMAIN,
            "play_media",
            {
                ATTR_ENTITY_ID: "media_player.amazon_fire",
                "media_content_type": "playlist",
                "media_content_id": "test.m4u",
            },
            blocking=True,
        )
    assert error.value.args[0] == "Unsupported media type playlist"


async def test_browse_media(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test Fully Kiosk browse media."""

    await async_setup_component(hass, MS_DOMAIN, {MS_DOMAIN: {}})
    await hass.async_block_till_done()

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "media_content_id": "media-source://media_source",
            "media_content_type": "library",
            "entity_id": "media_player.amazon_fire",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    expected_child_audio = {
        "title": "test.mp3",
        "media_class": "music",
        "media_content_type": "audio/mpeg",
        "media_content_id": "media-source://media_source/local/test.mp3",
        "can_play": True,
        "can_expand": False,
        "thumbnail": None,
        "children_media_class": None,
    }
    assert expected_child_audio in response["result"]["children"]
