"""Test the Fully Kiosk Browser media player."""
from unittest.mock import MagicMock

from homeassistant.components.fully_kiosk.const import DOMAIN, MEDIA_SUPPORT_FULLYKIOSK
import homeassistant.components.media_player as media_player
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_buttons(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test standard Fully Kiosk buttons."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("media_player.amazon_fire_media_player")
    assert state

    entry = entity_registry.async_get("media_player.amazon_fire_media_player")
    assert entry
    assert entry.unique_id == "abcdef-123456-mediaplayer"
    assert entry.supported_features == MEDIA_SUPPORT_FULLYKIOSK

    await hass.services.async_call(
        media_player.DOMAIN,
        "play_media",
        {
            ATTR_ENTITY_ID: "media_player.amazon_fire_media_player",
            "media_content_type": "music",
            "media_content_id": "test.mp3",
        },
        blocking=True,
    )
    assert len(mock_fully_kiosk.playSound.mock_calls) == 1

    await hass.services.async_call(
        media_player.DOMAIN,
        "media_stop",
        {
            ATTR_ENTITY_ID: "media_player.amazon_fire_media_player",
        },
        blocking=True,
    )
    assert len(mock_fully_kiosk.stopSound.mock_calls) == 1

    await hass.services.async_call(
        media_player.DOMAIN,
        "volume_set",
        {
            ATTR_ENTITY_ID: "media_player.amazon_fire_media_player",
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
