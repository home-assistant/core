"""The Bravia TV component."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
import logging
from typing import Final

import aiohttp
from pybravia import BraviaTV

from homeassistant.components.media_player.const import MEDIA_TYPE_CHANNEL
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
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

    session = async_create_clientsession(
        hass, cookie_jar=aiohttp.CookieJar(unsafe=True)
    )
    client = BraviaTV(host, mac, session=session)
    coordinator = BraviaTVCoordinator(hass, client, pin, ignored_sources)
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

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
        client: BraviaTV,
        pin: str,
        ignored_sources: list[str],
    ) -> None:
        """Initialize Bravia TV Client."""

        self.client = client
        self.pin = pin
        self.ignored_sources = ignored_sources
        self.source: str | None = None
        self.source_list: list[str] = []
        self.source_map: dict[str, dict] = {}
        self.media_title: str | None = None
        self.media_content_id: str | None = None
        self.media_content_type: str | None = None
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

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=1.0, immediate=False
            ),
        )

    def _sources_extend(self, sources: dict, source_type: str) -> None:
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
        power_status = await self.client.get_power_status()

        if power_status == "off":
            self.connected = False
        else:
            if not self.connected:
                self.connected = await self.client.connect(
                    pin=self.pin, clientid=CLIENTID_PREFIX, nickname=NICKNAME
                )

        self.is_on = self.connected and power_status == "active"

        if self.is_on is False:
            return

        if not self.source_map:
            await self._async_update_sources()
        await self._async_update_volume()
        await self._async_update_playing()

    async def _async_update_sources(self) -> None:
        """Update sources."""
        self.source_list = []
        self.source_map = {}

        externals = await self.client.get_external_status()
        self._sources_extend(externals, "input")

        apps = await self.client.get_app_list()
        self._sources_extend(apps, "app")

        channels = await self.client.get_content_list_all("tv")
        self._sources_extend(channels, "channel")

    async def _async_update_volume(self) -> None:
        """Update volume information."""
        volume_info = await self.client.get_volume_info()
        volume_level = volume_info.get("volume")
        if volume_level is not None:
            self.volume_level = volume_level / 100
            self.volume_muted = volume_info.get("mute", False)
            self.volume_target = volume_info.get("target")

    async def _async_update_playing(self) -> None:
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
                self.media_content_type = MEDIA_TYPE_CHANNEL
            else:
                self.media_content_id = self.media_uri
                self.media_content_type = None
        else:
            self.source = None
            self.is_channel = False
            self.media_content_id = None
            self.media_content_type = None
        if not playing_info:
            self.media_title = "App"

    async def async_turn_on(self) -> None:
        """Turn the device on."""
        await self.client.turn_on()
        await self.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn off device."""
        await self.client.turn_off()
        await self.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.client.volume_level(round(volume * 100))
        await self.async_request_refresh()

    async def async_volume_up(self) -> None:
        """Send volume up command to device."""
        await self.client.volume_up()
        await self.async_request_refresh()

    async def async_volume_down(self) -> None:
        """Send volume down command to device."""
        await self.client.volume_down()
        await self.async_request_refresh()

    async def async_volume_mute(self, mute: bool) -> None:
        """Send mute command to device."""
        await self.client.volume_mute()
        await self.async_request_refresh()

    async def async_media_play(self) -> None:
        """Send play command to device."""
        await self.client.play()
        self.playing = True
        await self.async_request_refresh()

    async def async_media_pause(self) -> None:
        """Send pause command to device."""
        await self.client.pause()
        self.playing = False
        await self.async_request_refresh()

    async def async_media_stop(self) -> None:
        """Send stop command to device."""
        await self.client.stop()
        await self.async_request_refresh()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        if self.is_channel:
            await self.client.channel_up()
        else:
            await self.client.next_track()
        await self.async_request_refresh()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        if self.is_channel:
            await self.client.channel_down()
        else:
            await self.client.previous_track()
        await self.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        """Set the input source."""
        for uri, item in self.source_map.items():
            if item.get("title") == source:
                if item.get("type") == "app":
                    await self.client.set_active_app(uri)
                else:
                    await self.client.set_play_content(uri)
                break

    async def async_send_command(self, command: Iterable[str], repeats: int) -> None:
        """Send command to device."""
        for _ in range(repeats):
            for cmd in command:
                await self.client.send_command(cmd)
        await self.async_request_refresh()
