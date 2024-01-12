"""Update coordinator for Bravia TV integration."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine, Iterable
from datetime import timedelta
from functools import wraps
import logging
from types import MappingProxyType
from typing import Any, Concatenate, Final, ParamSpec, TypeVar

from pybravia import (
    BraviaAuthError,
    BraviaClient,
    BraviaConnectionError,
    BraviaConnectionTimeout,
    BraviaError,
    BraviaNotFound,
    BraviaTurnedOff,
)

from homeassistant.components.media_player import MediaType
from homeassistant.const import CONF_CLIENT_ID, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_NICKNAME,
    CONF_USE_PSK,
    DOMAIN,
    LEGACY_CLIENT_ID,
    NICKNAME_PREFIX,
    SourceType,
)

_BraviaTVCoordinatorT = TypeVar("_BraviaTVCoordinatorT", bound="BraviaTVCoordinator")
_P = ParamSpec("_P")
_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL: Final = timedelta(seconds=10)


def catch_braviatv_errors(
    func: Callable[Concatenate[_BraviaTVCoordinatorT, _P], Awaitable[None]],
) -> Callable[Concatenate[_BraviaTVCoordinatorT, _P], Coroutine[Any, Any, None]]:
    """Catch Bravia errors."""

    @wraps(func)
    async def wrapper(
        self: _BraviaTVCoordinatorT,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None:
        """Catch Bravia errors and log message."""
        try:
            await func(self, *args, **kwargs)
        except BraviaError as err:
            _LOGGER.error("Command error: %s", err)
        await self.async_request_refresh()

    return wrapper


class BraviaTVCoordinator(DataUpdateCoordinator[None]):
    """Representation of a Bravia TV Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: BraviaClient,
        config: MappingProxyType[str, Any],
    ) -> None:
        """Initialize Bravia TV Client."""

        self.client = client
        self.pin = config[CONF_PIN]
        self.use_psk = config.get(CONF_USE_PSK, False)
        self.client_id = config.get(CONF_CLIENT_ID, LEGACY_CLIENT_ID)
        self.nickname = config.get(CONF_NICKNAME, NICKNAME_PREFIX)
        self.source: str | None = None
        self.source_list: list[str] = []
        self.source_map: dict[str, dict] = {}
        self.media_title: str | None = None
        self.media_channel: str | None = None
        self.media_content_id: str | None = None
        self.media_content_type: MediaType | None = None
        self.media_uri: str | None = None
        self.media_duration: int | None = None
        self.volume_level: float | None = None
        self.volume_target: str | None = None
        self.volume_muted = False
        self.is_on = False
        self.connected = False
        self.skipped_updates = 0

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=1.0, immediate=False
            ),
        )

    def _sources_extend(
        self,
        sources: list[dict],
        source_type: SourceType,
        add_to_list: bool = False,
        sort_by: str | None = None,
    ) -> None:
        """Extend source map and source list."""
        if sort_by:
            sources = sorted(sources, key=lambda d: d.get(sort_by, ""))
        for item in sources:
            title = item.get("title")
            uri = item.get("uri")
            if not title or not uri:
                continue
            self.source_map[uri] = {**item, "type": source_type}
            if add_to_list and title not in self.source_list:
                self.source_list.append(title)

    async def _async_update_data(self) -> None:
        """Connect and fetch data."""
        try:
            if not self.connected:
                try:
                    if self.use_psk:
                        await self.client.connect(psk=self.pin)
                    else:
                        await self.client.connect(
                            pin=self.pin,
                            clientid=self.client_id,
                            nickname=self.nickname,
                        )
                    self.connected = True
                except BraviaAuthError as err:
                    raise ConfigEntryAuthFailed from err

            power_status = await self.client.get_power_status()
            self.is_on = power_status == "active"
            self.skipped_updates = 0

            if self.is_on is False:
                return

            if not self.source_map:
                await self.async_update_sources()
            await self.async_update_volume()
            await self.async_update_playing()
        except BraviaNotFound as err:
            if self.skipped_updates < 10:
                self.connected = False
                self.skipped_updates += 1
                _LOGGER.debug("Update skipped, Bravia API service is reloading")
                return
            raise UpdateFailed("Error communicating with device") from err
        except (BraviaConnectionError, BraviaConnectionTimeout, BraviaTurnedOff):
            self.is_on = False
            self.connected = False
            _LOGGER.debug("Update skipped, Bravia TV is off")
        except BraviaError as err:
            self.is_on = False
            self.connected = False
            raise UpdateFailed("Error communicating with device") from err

    async def async_update_volume(self) -> None:
        """Update volume information."""
        volume_info = await self.client.get_volume_info()
        if (volume_level := volume_info.get("volume")) is not None:
            self.volume_level = volume_level / 100
            self.volume_muted = volume_info.get("mute", False)
            self.volume_target = volume_info.get("target")

    async def async_update_playing(self) -> None:
        """Update current playing information."""
        playing_info = await self.client.get_playing_info()
        self.media_title = playing_info.get("title")
        self.media_uri = playing_info.get("uri")
        self.media_duration = playing_info.get("durationSec")
        self.media_channel = None
        self.media_content_id = None
        self.media_content_type = None
        self.source = None
        if self.media_uri:
            self.media_content_id = self.media_uri
            if self.media_uri[:8] == "extInput":
                self.source = playing_info.get("title")
            if self.media_uri[:2] == "tv":
                self.media_content_id = playing_info.get("dispNum")
                self.media_title = (
                    playing_info.get("programTitle") or self.media_content_id
                )
                self.media_channel = playing_info.get("title") or self.media_content_id
                self.media_content_type = MediaType.CHANNEL
        if not playing_info:
            self.media_title = "Smart TV"
            self.media_content_type = MediaType.APP

    async def async_update_sources(self) -> None:
        """Update all sources."""
        self.source_list = []
        self.source_map = {}

        inputs = await self.client.get_external_status()
        self._sources_extend(inputs, SourceType.INPUT, add_to_list=True)

        apps = await self.client.get_app_list()
        self._sources_extend(apps, SourceType.APP, sort_by="title")

        channels = await self.client.get_content_list_all("tv")
        self._sources_extend(channels, SourceType.CHANNEL)

    async def async_source_start(self, uri: str, source_type: SourceType | str) -> None:
        """Select source by uri."""
        if source_type == SourceType.APP:
            await self.client.set_active_app(uri)
        else:
            await self.client.set_play_content(uri)

    async def async_source_find(
        self, query: str, source_type: SourceType | str
    ) -> None:
        """Find and select source by query."""
        if query.startswith(("extInput:", "tv:", "com.sony.dtv.")):
            return await self.async_source_start(query, source_type)
        coarse_uri = None
        is_numeric_search = source_type == SourceType.CHANNEL and query.isnumeric()
        for uri, item in self.source_map.items():
            if item["type"] == source_type:
                if is_numeric_search:
                    num = item.get("dispNum")
                    if num and int(query) == int(num):
                        return await self.async_source_start(uri, source_type)
                else:
                    title: str = item["title"]
                    if query.lower() == title.lower():
                        return await self.async_source_start(uri, source_type)
                    if query.lower() in title.lower():
                        coarse_uri = uri
        if coarse_uri:
            return await self.async_source_start(coarse_uri, source_type)
        raise ValueError(f"Not found {source_type}: {query}")

    @catch_braviatv_errors
    async def async_turn_on(self) -> None:
        """Turn the device on."""
        await self.client.turn_on()

    @catch_braviatv_errors
    async def async_turn_off(self) -> None:
        """Turn off device."""
        await self.client.turn_off()

    @catch_braviatv_errors
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.client.volume_level(round(volume * 100))

    @catch_braviatv_errors
    async def async_volume_up(self) -> None:
        """Send volume up command to device."""
        await self.client.volume_up()

    @catch_braviatv_errors
    async def async_volume_down(self) -> None:
        """Send volume down command to device."""
        await self.client.volume_down()

    @catch_braviatv_errors
    async def async_volume_mute(self, mute: bool) -> None:
        """Send mute command to device."""
        await self.client.volume_mute()

    @catch_braviatv_errors
    async def async_media_play(self) -> None:
        """Send play command to device."""
        await self.client.play()

    @catch_braviatv_errors
    async def async_media_pause(self) -> None:
        """Send pause command to device."""
        await self.client.pause()

    @catch_braviatv_errors
    async def async_media_stop(self) -> None:
        """Send stop command to device."""
        await self.client.stop()

    @catch_braviatv_errors
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        if self.media_content_type == MediaType.CHANNEL:
            await self.client.channel_up()
        else:
            await self.client.next_track()

    @catch_braviatv_errors
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        if self.media_content_type == MediaType.CHANNEL:
            await self.client.channel_down()
        else:
            await self.client.previous_track()

    @catch_braviatv_errors
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        if media_type not in (MediaType.APP, MediaType.CHANNEL):
            raise ValueError(f"Invalid media type: {media_type}")
        await self.async_source_find(media_id, media_type)

    @catch_braviatv_errors
    async def async_select_source(self, source: str) -> None:
        """Set the input source."""
        await self.async_source_find(source, SourceType.INPUT)

    @catch_braviatv_errors
    async def async_send_command(self, command: Iterable[str], repeats: int) -> None:
        """Send command to device."""
        for _ in range(repeats):
            for cmd in command:
                response = await self.client.send_command(cmd)
                if not response:
                    commands = await self.client.get_command_list()
                    commands_keys = ", ".join(commands.keys())
                    # Logging an error instead of raising a ValueError
                    # https://github.com/home-assistant/core/pull/77329#discussion_r955768245
                    _LOGGER.error(
                        "Unsupported command: %s, list of available commands: %s",
                        cmd,
                        commands_keys,
                    )

    @catch_braviatv_errors
    async def async_reboot_device(self) -> None:
        """Send command to reboot the device."""
        await self.client.reboot()

    @catch_braviatv_errors
    async def async_terminate_apps(self) -> None:
        """Send command to terminate all applications."""
        await self.client.terminate_apps()
