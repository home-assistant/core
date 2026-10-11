"""Tests for the Kodi integration."""

from typing import Any
from unittest.mock import MagicMock, patch

from homeassistant.components.kodi.const import CONF_WS_PORT, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .util import MockConnection

from tests.common import MockConfigEntry, async_load_json_object_fixture

VIDEO_PLAYER = {"playerid": 1, "type": "video"}
AUDIO_PLAYER = {"playerid": 0, "type": "audio"}

PLAYER_PROPERTIES: dict[str, Any] = {
    "time": {"hours": 1, "minutes": 10, "seconds": 5, "milliseconds": 71},
    "totaltime": {"hours": 1, "minutes": 30, "seconds": 0, "milliseconds": 672},
    "speed": 1,
    "live": False,
}
OTHER_PLAYER_PROPERTIES: dict[str, Any] = {
    "time": {"hours": 0, "minutes": 0, "seconds": 0, "milliseconds": 0},
    "totaltime": {"hours": 0, "minutes": 0, "seconds": 0, "milliseconds": 0},
    "speed": 0,
    "live": False,
}
OTHER_PLAYER_ITEM: dict[str, Any] = {"id": 5, "type": "song", "label": "Other player"}

# Kodi returns these item fields even when they are not requested
ITEM_BASE_FIELDS = ("id", "label", "type")


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Kodi integration in Home Assistant."""
    entry_data = {
        CONF_NAME: "name",
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 8080,
        CONF_WS_PORT: 9090,
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
        CONF_SSL: False,
    }
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, title="name")
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.kodi.Kodi.ping", return_value=True),
        patch(
            "homeassistant.components.kodi.Kodi.get_application_properties",
            return_value={"version": {"major": 1, "minor": 1}},
        ),
        patch(
            "homeassistant.components.kodi.get_kodi_connection",
            return_value=MockConnection(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Kodi integration using the connection and client fixtures."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def set_playing(
    hass: HomeAssistant,
    mock_kodi: MagicMock,
    item: dict[str, Any] | None = None,
    players: list[dict[str, Any]] | None = None,
    **properties: Any,
) -> None:
    """Make Kodi report a playing item.

    The movie fixture plays on the video player unless another item or other
    players are given. Like Kodi, only the requested fields are returned, and
    the item and the properties belong to the first active player.
    """
    playing_item = (
        await async_load_json_object_fixture(hass, "movie.json", DOMAIN)
        if item is None
        else item
    )
    active_players = players or [VIDEO_PLAYER]
    player_properties = PLAYER_PROPERTIES | properties

    def get_player_properties(
        player: dict[str, Any], requested: list[str]
    ) -> dict[str, Any]:
        source = (
            player_properties
            if player == active_players[0]
            else OTHER_PLAYER_PROPERTIES
        )
        return {key: source[key] for key in requested}

    def get_playing_item_properties(
        player: dict[str, Any], requested: list[str]
    ) -> dict[str, Any]:
        source = playing_item if player == active_players[0] else OTHER_PLAYER_ITEM
        return {
            key: value
            for key, value in source.items()
            if key in requested or key in ITEM_BASE_FIELDS
        }

    mock_kodi.get_players.return_value = active_players
    mock_kodi.get_player_properties.side_effect = get_player_properties
    mock_kodi.get_playing_item_properties.side_effect = get_playing_item_properties


def set_idle(mock_kodi: MagicMock) -> None:
    """Make Kodi report that nothing is playing."""
    mock_kodi.get_players.return_value = []
