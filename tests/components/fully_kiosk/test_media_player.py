"""Test the Fully Kiosk Browser media player."""
from unittest.mock import MagicMock, Mock, patch

from homeassistant.components.fully_kiosk.const import DOMAIN, MEDIA_SUPPORT_FULLYKIOSK
import homeassistant.components.media_player as media_player
from homeassistant.components.media_source import DOMAIN as MS_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
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
