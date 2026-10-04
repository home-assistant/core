"""Tests for the Kodi media player."""

from unittest.mock import AsyncMock

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_component

from . import init_integration


class _KodiEventItem(dict):
    """Dict-like Kodi event item that also exposes an id attribute."""

    @property
    def id(self) -> int:
        return self["id"]


def _get_kodi_entity(hass: HomeAssistant, entity_id: str):
    """Return the loaded Kodi media player entity."""
    return hass.data[entity_component.DATA_INSTANCES]["media_player"].get_entity(
        entity_id
    )


async def test_picture_player_state_is_playing_when_slideshow_not_paused(
    hass: HomeAssistant,
) -> None:
    """Picture slideshows report playing when not paused."""
    await init_integration(hass)
    entity_id = "media_player.name"
    entity = _get_kodi_entity(hass, entity_id)

    entity._kodi.get_players = AsyncMock(
        return_value=[{"playerid": 2, "type": "picture"}]
    )
    entity._kodi.get_application_properties = AsyncMock(
        return_value={"volume": 50, "muted": False}
    )
    entity._kodi.get_player_properties = AsyncMock(
        return_value={
            "time": {"hours": 0, "minutes": 0, "seconds": 0, "milliseconds": 0},
            "totaltime": {"hours": 0, "minutes": 0, "seconds": 0, "milliseconds": 0},
            "speed": 0,
            "live": False,
        }
    )
    entity._kodi.call_method = AsyncMock(return_value={"Slideshow.IsPaused": "false"})
    entity._kodi.get_playing_item_properties = AsyncMock(
        return_value={"file": "image.jpg"}
    )

    await entity_component.async_update_entity(hass, entity_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == MediaPlayerState.PLAYING


async def test_picture_player_state_is_paused_when_slideshow_paused(
    hass: HomeAssistant,
) -> None:
    """Paused picture slideshows report paused."""
    await init_integration(hass)
    entity_id = "media_player.name"
    entity = _get_kodi_entity(hass, entity_id)

    entity._kodi.get_players = AsyncMock(
        return_value=[{"playerid": 2, "type": "picture"}]
    )
    entity._kodi.get_application_properties = AsyncMock(
        return_value={"volume": 50, "muted": False}
    )
    entity._kodi.get_player_properties = AsyncMock(
        return_value={
            "time": {"hours": 0, "minutes": 0, "seconds": 0, "milliseconds": 0},
            "totaltime": {"hours": 0, "minutes": 0, "seconds": 0, "milliseconds": 0},
            "speed": 0,
            "live": False,
        }
    )
    entity._kodi.call_method = AsyncMock(return_value={"Slideshow.IsPaused": "true"})
    entity._kodi.get_playing_item_properties = AsyncMock(
        return_value={"file": "image.jpg"}
    )

    await entity_component.async_update_entity(hass, entity_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == MediaPlayerState.PAUSED


async def test_async_update_fetches_picture_slideshow_pause_state(
    hass: HomeAssistant,
) -> None:
    """Picture player updates use Kodi's slideshow pause boolean."""
    await init_integration(hass)
    entity_id = "media_player.name"
    entity = _get_kodi_entity(hass, entity_id)

    entity._kodi.get_players = AsyncMock(
        return_value=[{"playerid": 2, "type": "picture"}]
    )
    entity._kodi.get_application_properties = AsyncMock(
        return_value={"volume": 50, "muted": False}
    )
    entity._kodi.get_player_properties = AsyncMock(
        return_value={
            "time": {"hours": 0, "minutes": 0, "seconds": 0, "milliseconds": 0},
            "totaltime": {"hours": 0, "minutes": 0, "seconds": 0, "milliseconds": 0},
            "speed": 0,
            "live": False,
        }
    )
    entity._kodi.call_method = AsyncMock(return_value={"Slideshow.IsPaused": "false"})
    entity._kodi.get_playing_item_properties = AsyncMock(
        return_value={"file": "image.jpg"}
    )

    await entity.async_update()

    entity._kodi.call_method.assert_awaited_once_with(
        "XBMC.GetInfoBooleans", booleans=["Slideshow.IsPaused"]
    )
    assert entity.state is MediaPlayerState.PLAYING


async def test_picture_pause_event_updates_loaded_entity_state(
    hass: HomeAssistant,
) -> None:
    """Picture pause events update slideshow pause state without a full refresh."""
    await init_integration(hass)
    entity_id = "media_player.name"
    entity = _get_kodi_entity(hass, entity_id)

    entity._players = [{"playerid": 2, "type": "picture"}]
    entity._properties = {"speed": 1}
    entity._item = {"id": 7}
    entity._slideshow_is_paused = False
    entity._app_properties = {"volume": 50, "muted": False}
    entity.async_write_ha_state()

    entity.async_on_speed_event(
        "OnPause",
        {
            "player": {"speed": 0},
            "item": _KodiEventItem({"id": 7, "type": "picture"}),
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == MediaPlayerState.PAUSED
    assert entity._slideshow_is_paused is True


async def test_picture_play_event_keeps_non_slideshow_images_playing(
    hass: HomeAssistant,
) -> None:
    """Picture OnPlay with speed 0 does not force a paused slideshow state."""
    await init_integration(hass)
    entity_id = "media_player.name"
    entity = _get_kodi_entity(hass, entity_id)

    entity._players = [{"playerid": 2, "type": "picture"}]
    entity._properties = {"speed": 0}
    entity._item = {"id": 7}
    entity._slideshow_is_paused = False
    entity._app_properties = {"volume": 50, "muted": False}
    entity.async_write_ha_state()

    entity.async_on_speed_event(
        "OnPlay",
        {
            "player": {"speed": 0},
            "item": _KodiEventItem({"id": 7, "type": "picture"}),
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == MediaPlayerState.PLAYING
    assert entity._slideshow_is_paused is False
