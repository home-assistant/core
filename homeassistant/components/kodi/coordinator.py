"""Shared playback data for Kodi stream entities."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from math import isfinite
from typing import TYPE_CHECKING, Any, override

from jsonrpc_base.jsonrpc import ProtocolError, TransportError
from pykodi import CannotConnectError, InvalidAuthError, Kodi
from pykodi.kodi import KodiHTTPConnection, KodiWSConnection

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from . import KodiConfigEntry

_LOGGER = logging.getLogger(__name__)


class KodiPlaybackCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll active stream information without depending on the media player entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: KodiConfigEntry,
        connection: KodiHTTPConnection | KodiWSConnection,
        kodi: Kodi,
    ) -> None:
        """Initialize the playback updater."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Kodi playback",
            update_interval=timedelta(seconds=10),
            always_update=False,
        )
        self.connection = connection
        self.kodi = kodi
        self.data = {}
        self._connect_lock = asyncio.Lock()
        self._connection_listeners: set[Callable[[], Awaitable[None]]] = set()

    @callback
    def async_add_connection_listener(
        self, listener: Callable[[], Awaitable[None]]
    ) -> Callable[[], None]:
        """Subscribe to successful reconnects."""
        self._connection_listeners.add(listener)
        return lambda: self._connection_listeners.remove(listener)

    async def async_connect(self) -> None:
        """Serialize reconnects with the media player watchdog."""
        async with self._connect_lock:
            if not self.connection.connected:
                await self.connection.connect()
                for listener in tuple(self._connection_listeners):
                    await listener()

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Read the video player, or the audio player when there is no video."""
        try:
            await self.async_connect()
            players = await self.kodi.get_players()
            player = next(
                (
                    player
                    for player_type in ("video", "audio")
                    for player in players or []
                    if player["type"] == player_type
                ),
                None,
            )
            data: dict[str, Any] = {}
            try:
                opacity = await self.kodi.call_method(
                    "Settings.GetSettingValue", setting="subtitles.opacity"
                )
            except ProtocolError as err:
                _LOGGER.debug("Subtitle opacity is unavailable: %s", err)
            else:
                data["subtitle_opacity"] = opacity["value"]
            try:
                margin = await self.kodi.call_method(
                    "Settings.GetSettingValue", setting="subtitles.marginvertical"
                )
            except ProtocolError as err:
                _LOGGER.debug("Subtitle vertical margin is unavailable: %s", err)
            else:
                data["subtitle_margin"] = margin["value"]
            if player is None:
                return data
            properties = ["currentaudiostream", "audiostreams"]
            if player["type"] == "video":
                properties.extend(
                    [
                        "currentvideostream",
                        "currentsubtitle",
                        "subtitles",
                        "subtitleenabled",
                    ]
                )
            data.update(
                {
                    "player": player,
                    **await self.kodi.get_player_properties(player, properties),
                }
            )
            if player["type"] == "video":
                try:
                    viewmode = await self.kodi.call_method("Player.GetViewMode")
                except ProtocolError as err:
                    _LOGGER.debug("Picture view mode is unavailable: %s", err)
                else:
                    data["viewmode"] = viewmode
                    data["picture_vertical_shift"] = viewmode.get("verticalshift")
                try:
                    labels = await self.kodi.call_method(
                        "XBMC.GetInfoLabels",
                        labels=[
                            "Player.Process(VideoFPS)",
                            "Player.AudioDelay",
                            "Player.SubtitleDelay",
                            "Player.Chapter",
                            "Player.ChapterCount",
                            "Player.ChapterName",
                            "VideoPlayer.HdrType",
                        ],
                    )
                except ProtocolError as err:
                    _LOGGER.debug("Kodi video info labels are unavailable: %s", err)
                else:
                    data.update(_parse_info_labels(labels))
                try:
                    alignment = await self.kodi.call_method(
                        "Settings.GetSettingValue", setting="subtitles.align"
                    )
                except ProtocolError as err:
                    _LOGGER.debug("Subtitle alignment is unavailable: %s", err)
                else:
                    data["subtitle_alignment"] = alignment["value"]
        except InvalidAuthError as err:
            raise ConfigEntryAuthFailed from err
        except (CannotConnectError, TransportError, ProtocolError) as err:
            raise UpdateFailed(str(err)) from err
        return data

    async def async_get_setting_default(self, setting_id: str) -> Any:
        """Read a setting's configured Kodi default for reset controls."""
        result = await self.kodi.call_method("Settings.GetSettings", level="expert")
        settings = result.get("settings", [])
        setting = next(
            (item for item in settings if item.get("id") == setting_id), None
        )
        if setting is None or "default" not in setting:
            raise ProtocolError(-32602, f"No default found for {setting_id}", None)
        return setting["default"]


def _parse_info_labels(labels: dict[str, Any]) -> dict[str, Any]:
    """Parse optional playback labels returned by Kodi."""
    data: dict[str, Any] = {}
    for key, label in (
        ("audio_delay", "Player.AudioDelay"),
        ("subtitle_delay", "Player.SubtitleDelay"),
    ):
        try:
            value = float(str(labels[label]).removesuffix("s").strip())
        except KeyError, TypeError, ValueError:
            _LOGGER.debug("Kodi %s is unavailable", key.replace("_", " "))
        else:
            if isfinite(value):
                data[key] = value
    fps = labels.get("Player.Process(VideoFPS)")
    try:
        data["video_fps"] = float(fps) if fps else None
    except TypeError, ValueError:
        data["video_fps"] = None
    hdr_type = labels.get("VideoPlayer.HdrType")
    data["video_hdr_type"] = (
        hdr_type.lower() if isinstance(hdr_type, str) and hdr_type else None
    )
    chapter_name = labels.get("Player.ChapterName")
    if isinstance(chapter_name, str) and chapter_name:
        data["chapter_name"] = chapter_name
    for key, label in (
        ("chapter_number", "Player.Chapter"),
        ("chapter_count", "Player.ChapterCount"),
    ):
        try:
            value = int(labels[label])
        except KeyError, TypeError, ValueError:
            _LOGGER.debug("Kodi %s is unavailable", key.replace("_", " "))
        else:
            data[key] = value
    return data
