"""The Bravia TV component."""
import asyncio
from datetime import timedelta
import logging

from bravia_tv import BraviaRC
from bravia_tv.braviarc import NoIPControl

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CLIENTID_PREFIX, CONF_IGNORED_SOURCES, DOMAIN, NICKNAME

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [MEDIA_PLAYER_DOMAIN, REMOTE_DOMAIN]
SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(hass, config_entry):
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


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def update_listener(hass, config_entry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class BraviaTVCoordinator(DataUpdateCoordinator[None]):
    """Representation of a Bravia TV Coordinator.

    An instance is used per device to share the same power state between
    several platforms.
    """

    def __init__(self, hass, host, mac, pin, ignored_sources):
        """Initialize Bravia TV Client."""

        self.braviarc = BraviaRC(host, mac)
        self.pin = pin
        self.ignored_sources = ignored_sources
        self.muted = False
        self.channel_name = None
        self.channel_number = None
        self.media_title = None
        self.source = None
        self.source_list = []
        self.original_content_list = []
        self.content_mapping = {}
        self.duration = None
        self.content_uri = None
        self.start_date_time = None
        self.program_media_type = None
        self.audio_output = None
        self.min_volume = None
        self.max_volume = None
        self.volume_level = None
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

    def _send_command(self, command, repeats=1):
        """Send a command to the TV."""
        for _ in range(repeats):
            for cmd in command:
                self.braviarc.send_command(cmd)

    def _get_source(self):
        """Return the name of the source."""
        for key, value in self.content_mapping.items():
            if value == self.content_uri:
                return key

    def _refresh_volume(self):
        """Refresh volume information."""
        volume_info = self.braviarc.get_volume_info(self.audio_output)
        if volume_info is not None:
            volume = volume_info.get("volume")
            self.volume_level = volume / 100 if volume is not None else None
            self.audio_output = volume_info.get("target")
            self.min_volume = volume_info.get("minVolume")
            self.max_volume = volume_info.get("maxVolume")
            self.muted = volume_info.get("mute")
            return True
        return False

    def _refresh_channels(self):
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

    def _refresh_playing_info(self):
        """Refresh playing information."""
        playing_info = self.braviarc.get_playing_info()
        program_name = playing_info.get("programTitle")
        self.channel_name = playing_info.get("title")
        self.program_media_type = playing_info.get("programMediaType")
        self.channel_number = playing_info.get("dispNum")
        self.content_uri = playing_info.get("uri")
        self.source = self._get_source()
        self.duration = playing_info.get("durationSec")
        self.start_date_time = playing_info.get("startDateTime")
        if not playing_info:
            self.channel_name = "App"
        if self.channel_name is not None:
            self.media_title = self.channel_name
            if program_name is not None:
                self.media_title = f"{self.media_title}: {program_name}"
        else:
            self.media_title = None

    def _update_tv_data(self):
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

    async def _async_update_data(self):
        """Fetch the latest data."""
        if self.state_lock.locked():
            return

        await self.hass.async_add_executor_job(self._update_tv_data)

    async def async_turn_on(self):
        """Turn the device on."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self.braviarc.turn_on)
            await self.async_request_refresh()

    async def async_turn_off(self):
        """Turn off device."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self.braviarc.turn_off)
            await self.async_request_refresh()

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(
                self.braviarc.set_volume_level, volume, self.audio_output
            )
            await self.async_request_refresh()

    async def async_volume_up(self):
        """Send volume up command to device."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(
                self.braviarc.volume_up, self.audio_output
            )
            await self.async_request_refresh()

    async def async_volume_down(self):
        """Send volume down command to device."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(
                self.braviarc.volume_down, self.audio_output
            )
            await self.async_request_refresh()

    async def async_volume_mute(self, mute):
        """Send mute command to device."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self.braviarc.mute_volume, mute)
            await self.async_request_refresh()

    async def async_media_play(self):
        """Send play command to device."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self.braviarc.media_play)
            self.playing = True
            await self.async_request_refresh()

    async def async_media_pause(self):
        """Send pause command to device."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self.braviarc.media_pause)
            self.playing = False
            await self.async_request_refresh()

    async def async_media_stop(self):
        """Send stop command to device."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self.braviarc.media_stop)
            self.playing = False
            await self.async_request_refresh()

    async def async_media_next_track(self):
        """Send next track command."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self.braviarc.media_next_track)
            await self.async_request_refresh()

    async def async_media_previous_track(self):
        """Send previous track command."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self.braviarc.media_previous_track)
            await self.async_request_refresh()

    async def async_select_source(self, source):
        """Set the input source."""
        if source in self.content_mapping:
            uri = self.content_mapping[source]
            async with self.state_lock:
                await self.hass.async_add_executor_job(self.braviarc.play_content, uri)
                await self.async_request_refresh()

    async def async_send_command(self, command, repeats):
        """Send command to device."""
        async with self.state_lock:
            await self.hass.async_add_executor_job(self._send_command, command, repeats)
            await self.async_request_refresh()
