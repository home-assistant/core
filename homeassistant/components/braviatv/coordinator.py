"""Update coordinator for Bravia TV integration."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine, Iterable
from datetime import timedelta
from functools import wraps
import logging
from typing import Any, Final, TypeVar

from pybravia import (
    BraviaTV,
    BraviaTVConnectionError,
    BraviaTVConnectionTimeout,
    BraviaTVError,
    BraviaTVNotFound,
    BraviaTVTurnedOff,
)
from typing_extensions import Concatenate, ParamSpec

from homeassistant.components.media_player import MediaType
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CLIENTID_PREFIX, DOMAIN, NICKNAME

_BraviaTVCoordinatorT = TypeVar("_BraviaTVCoordinatorT", bound="BraviaTVCoordinator")
_P = ParamSpec("_P")
_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL: Final = timedelta(seconds=10)


def catch_braviatv_errors(
    func: Callable[Concatenate[_BraviaTVCoordinatorT, _P], Awaitable[None]]
) -> Callable[Concatenate[_BraviaTVCoordinatorT, _P], Coroutine[Any, Any, None]]:
    """Catch BraviaTV errors."""

    @wraps(func)
    async def wrapper(
        self: _BraviaTVCoordinatorT,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None:
        """Catch BraviaTV errors and log message."""
        try:
            await func(self, *args, **kwargs)
        except BraviaTVError as err:
            _LOGGER.error("Command error: %s", err)
        await self.async_request_refresh()

    return wrapper


class BraviaTVCoordinator(DataUpdateCoordinator[None]):
    """Representation of a Bravia TV Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: BraviaTV,
        pin: str,
        use_psk: bool,
        ignored_sources: list[str],
    ) -> None:
        """Initialize Bravia TV Client."""

        self.client = client
        self.pin = pin
        self.use_psk = use_psk
        self.ignored_sources = ignored_sources
        self.source: str | None = None
        self.source_list: list[str] = []
        self.source_map: dict[str, dict] = {}
        self.media_title: str | None = None
        self.media_content_id: str | None = None
        self.media_content_type: MediaType | None = None
        self.media_uri: str | None = None
        self.media_duration: int | None = None
        self.volume_level: float | None = None
        self.volume_target: str | None = None
        self.volume_muted = False
        self.is_on = False
        self.is_channel = False
        self.connected = False
        # Assume that the TV is in Play mode
        self.playing = True
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

    def _sources_extend(self, sources: list[dict], source_type: str) -> None:
        """Extend source map and source list."""
        for item in sources:
            item["type"] = source_type
            title = item.get("title")
            uri = item.get("uri")
            if not title or not uri:
                continue
            self.source_map[uri] = item
            if title not in self.ignored_sources:
                self.source_list.append(title)

    async def _async_update_data(self) -> None:
        """Connect and fetch data."""
        try:
            if not self.connected:
                if self.use_psk:
                    await self.client.connect(psk=self.pin)
                else:
                    await self.client.connect(
                        pin=self.pin, clientid=CLIENTID_PREFIX, nickname=NICKNAME
                    )
                self.connected = True

            power_status = await self.client.get_power_status()
            self.is_on = power_status == "active"
            self.skipped_updates = 0

            if self.is_on is False:
                return

            if not self.source_map:
                await self.async_update_sources()
            await self.async_update_volume()
            await self.async_update_playing()
        except BraviaTVNotFound as err:
            if self.skipped_updates < 10:
                self.connected = False
                self.skipped_updates += 1
                _LOGGER.debug("Update skipped, Bravia API service is reloading")
                return
            raise UpdateFailed("Error communicating with device") from err
        except (BraviaTVConnectionError, BraviaTVConnectionTimeout, BraviaTVTurnedOff):
            self.is_on = False
            self.connected = False
            _LOGGER.debug("Update skipped, Bravia TV is off")
        except BraviaTVError as err:
            self.is_on = False
            self.connected = False
            raise UpdateFailed("Error communicating with device") from err

    async def async_update_sources(self) -> None:
        """Update sources."""
        self.source_list = []
        self.source_map = {}

        externals = await self.client.get_external_status()
        self._sources_extend(externals, "input")

        apps = await self.client.get_app_list()
        self._sources_extend(apps, "app")

        channels = await self.client.get_content_list_all("tv")
        self._sources_extend(channels, "channel")

    async def async_update_volume(self) -> None:
        """Update volume information."""
        volume_info = await self.client.get_volume_info()
        volume_level = volume_info.get("volume")
        if volume_level is not None:
            self.volume_level = volume_level / 100
            self.volume_muted = volume_info.get("mute", False)
            self.volume_target = volume_info.get("target")

    async def async_update_playing(self) -> None:
        """Update current playing information."""
        playing_info = await self.client.get_playing_info()
        self.media_title = playing_info.get("title")
        self.media_uri = playing_info.get("uri")
        self.media_duration = playing_info.get("durationSec")
        if program_title := playing_info.get("programTitle"):
            self.media_title = f"{self.media_title}: {program_title}"
        if self.media_uri:
            source = self.source_map.get(self.media_uri, {})
            self.source = source.get("title")
            self.is_channel = self.media_uri[:2] == "tv"
            if self.is_channel:
                self.media_content_id = playing_info.get("dispNum")
                self.media_content_type = MediaType.CHANNEL
            else:
                self.media_content_id = self.media_uri
                self.media_content_type = None
        else:
            self.source = None
            self.is_channel = False
            self.media_content_id = None
            self.media_content_type = None
        if not playing_info:
            self.media_title = "Smart TV"
            self.media_content_type = MediaType.APP

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
        self.playing = True

    @catch_braviatv_errors
    async def async_media_pause(self) -> None:
        """Send pause command to device."""
        await self.client.pause()
        self.playing = False

    @catch_braviatv_errors
    async def async_media_stop(self) -> None:
        """Send stop command to device."""
        await self.client.stop()

    @catch_braviatv_errors
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        if self.is_channel:
            await self.client.channel_up()
        else:
            await self.client.next_track()

    @catch_braviatv_errors
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        if self.is_channel:
            await self.client.channel_down()
        else:
            await self.client.previous_track()

    @catch_braviatv_errors
    async def async_select_source(self, source: str) -> None:
        """Set the input source."""
        for uri, item in self.source_map.items():
            if item.get("title") == source:
                if item.get("type") == "app":
                    await self.client.set_active_app(uri)
                else:
                    await self.client.set_play_content(uri)
                break

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
