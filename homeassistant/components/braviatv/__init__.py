"""The Bravia TV component."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import timedelta
import logging
from typing import Final

from bravia_tv import BraviaRC
from bravia_tv.braviarc import NoIPControl

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CLIENTID_PREFIX, CONF_IGNORED_SOURCES, DOMAIN, NICKNAME

_LOGGER = logging.getLogger(__name__)

PLATFORMS: Final[list[Platform]] = [Platform.MEDIA_PLAYER, Platform.REMOTE]
SCAN_INTERVAL: Final = timedelta(seconds=10)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    host = config_entry.data[CONF_HOST]
    mac = config_entry.data[CONF_MAC]
    pin = config_entry.data[CONF_PIN]
    ignored_sources = config_entry.options.get(CONF_IGNORED_SOURCES, [])

    coordinator = BraviaTVCoordinator(hass, host, mac, pin, ignored_sources)
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class BraviaTVCoordinator(DataUpdateCoordinator[None]):
    """Representation of a Bravia TV Coordinator.

    An instance is used per device to share the same power state between
    several platforms.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        mac: str,
        pin: str,
        ignored_sources: list[str],
    ) -> None:
        """Initialize Bravia TV Client."""

        self.braviarc = BraviaRC(host, mac)
        self.pin = pin
        self.ignored_sources = ignored_sources
        self.muted: bool = False
        self.channel_name: str | None = None
        self.media_title: str | None = None
        self.source: str | None = None
        self.source_list: list[str] = []
        self.original_content_list: list[str] = []
        self.content_mapping: dict[str, str] = {}
        self.duration: int | None = None
        self.content_uri: str | None = None
        self.program_media_type: str | None = None
        self.audio_output: str | None = None
        self.min_volume: int | None = None
        self.max_volume: int | None = None
        self.volume_level: float | None = None
        self.is_on = False
        # Assume that the TV is in Play mode
        self.playing = True
        self.state_lock = asyncio.Lock()

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=1.0, immediate=False
            ),
        )

    def _send_command(self, command: Iterable[str], repeats: int = 1) -> None:
        """Send a command to the TV."""
        for _ in range(repeats):
            for cmd in command:
                self.braviarc.send_command(cmd)

    def _get_source(self) -> str | None:
        """Return the name of the source."""
        for key, value in self.content_mapping.items():
            if value == self.content_uri:
                return key
        return None

    def _refresh_volume(self) -> bool:
        """Refresh volume information."""
        volume_info = self.braviarc.get_volume_info(self.audio_output)
        if volume_info is not None:
            volume = volume_info.get("volume")
            self.volume_level = volume / 100 if volume is not None else None
            self.audio_output = volume_info.get("target")
            self.min_volume = volume_info.get("minVolume")
            self.max_volume = volume_info.get("maxVolume")
            self.muted = volume_info.get("mute", False)
            return True
        return False

    def _refresh_channels(self) -> bool:
        """Refresh source and channels list."""
        if not self.source_list:
            self.content_mapping = self.braviarc.load_source_list()
            self.source_list = []
            if not self.content_mapping:
                return False
            for key in self.content_mapping:
                if key not in self.ignored_sources:
                    self.source_list.append(key)
        return True

    def _refresh_playing_info(self) -> None:
        """Refresh playing information."""
        playing_info = self.braviarc.get_playing_info()
        program_name = playing_info.get("programTitle")
        self.channel_name = playing_info.get("title")
        self.program_media_type = playing_info.get("programMediaType")
        self.content_uri = playing_info.get("uri")
        self.source = self._get_source()
        self.duration = playing_info.get("durationSec")
        if not playing_info:
            self.channel_name = "App"
        if self.channel_name is not None:
            self.media_title = self.channel_name
            if program_name is not None:
                self.media_title = f"{self.media_title}: {program_name}"
        else:
            self.media_title = None

    def _update_tv_data(self) -> None:
        """Connect and update TV info."""
        power_status = self.braviarc.get_power_status()

        if power_status != "off":
            connected = self.braviarc.is_connected()
            if not connected:
                try:
                    connected = self.braviarc.connect(
                        self.pin, CLIENTID_PREFIX, NICKNAME
                    )
                except NoIPControl:
                    _LOGGER.error("IP Control is disabled in the TV settings")
            if not connected:
                power_status = "off"

        if power_status == "active":
            self.is_on = True
            if self._refresh_volume() and self._refresh_channels():
                self._refresh_playing_info()
                return

        self.is_on = False

    async def _async_update_data(self) -> None:
        """Fetch the latest data."""
        if self.state_lock.locked():
            return

        await self.hass.async_add_executor_job(self._update_tv_data)

    async def async_turn_on(self) -> None:
        """Turn the device on."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self.braviarc.turn_on)
            await self.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn off device."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self.braviarc.turn_off)
            await self.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(
                self.braviarc.set_volume_level, volume, self.audio_output
            )
            await self.async_request_refresh()

    async def async_volume_up(self) -> None:
        """Send volume up command to device."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(
                self.braviarc.volume_up, self.audio_output
            )
            await self.async_request_refresh()

    async def async_volume_down(self) -> None:
        """Send volume down command to device."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(
                self.braviarc.volume_down, self.audio_output
            )
            await self.async_request_refresh()

    async def async_volume_mute(self, mute: bool) -> None:
        """Send mute command to device."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self.braviarc.mute_volume, mute)
            await self.async_request_refresh()

    async def async_media_play(self) -> None:
        """Send play command to device."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self.braviarc.media_play)
            self.playing = True
            await self.async_request_refresh()

    async def async_media_pause(self) -> None:
        """Send pause command to device."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self.braviarc.media_pause)
            self.playing = False
            await self.async_request_refresh()

    async def async_media_stop(self) -> None:
        """Send stop command to device."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self.braviarc.media_stop)
            self.playing = False
            await self.async_request_refresh()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self.braviarc.media_next_track)
            await self.async_request_refresh()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self.braviarc.media_previous_track)
            await self.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        """Set the input source."""
        if source in self.content_mapping:
            uri = self.content_mapping[source]
            async with self.state_lock:
                await self.hass.async_add_executor_job(self.braviarc.play_content, uri)
                await self.async_request_refresh()

    async def async_send_command(self, command: Iterable[str], repeats: int) -> None:
        """Send command to device."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self._send_command, command, repeats)
            await self.async_request_refresh()
