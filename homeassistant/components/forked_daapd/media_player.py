"""This library brings support for forked_daapd to Home Assistant."""
import asyncio
from collections import defaultdict
from functools import partialmethod
import logging

from pyforked_daapd import ForkedDaapdAPI, ForkedDaapdData
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerDevice
from homeassistant.components.media_player.const import (
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.util.dt import utcnow

_LOGGER = logging.getLogger(__name__)
SUPPORTED_FEATURES = (
    SUPPORT_PLAY
    | SUPPORT_PAUSE
    | SUPPORT_STOP
    | SUPPORT_SEEK
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
)

SUPPORTED_FEATURES_ZONE = (
    SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF
)

DOMAIN = "forked_daapd"
DEFAULT_PORT = 3689

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

WS_NOTIFY_EVENT_TYPES = ["player", "outputs", "volume", "options", "queue"]
DEFAULT_VOLUME = 0.5  # in range [0,1]
WEBSOCKET_RECONNECT_TIME = 30  # seconds


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the forked-daapd platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    entities = []
    forked_daapd_device = ForkedDaapdDevice(async_get_clientsession(hass), host, port)
    entities = await forked_daapd_device.async_init()
    if entities:
        async_add_entities(entities, True)


class ForkedDaapdZone(MediaPlayerDevice):
    """Representation of a forked-daapd output."""

    @property
    def should_poll(self) -> bool:
        """Entity pushes its state to HA."""
        return False

    async def async_toggle(self):
        """Toggle the power on the zone.

        Default media player component method counts idle as off - we consider idle to be on but just not playing.
        """
        if self.state == STATE_OFF:
            await self.async_turn_on()
        else:
            await self.async_turn_off()

    def __init__(self, master_device, output):
        """Initialize the ForkedDaapd Zone."""
        super(ForkedDaapdZone, self).__init__()
        _LOGGER.debug("New ForkedDaapdZone")
        self._master = master_device
        self._name = output["name"]
        self._output_id = output["id"]
        self._last_volume = DEFAULT_VOLUME  # used for mute/unmute

    async def async_turn_on(self):
        """Enable the output."""
        await self._master.turn_on_output(self._output_id)

    async def async_turn_off(self):
        """Disable the output."""
        await self._master.turn_off_output(self._output_id)

    @property
    def name(self):
        """Return the name of the zone."""
        return f"{self._master.name} ({self._name})"

    @property
    def state(self):
        """State of the zone."""
        if self._output_id not in self._master.get_selected():
            _LOGGER.debug("Zone state is STATE_OFF")
            return STATE_OFF
        _LOGGER.debug("Zone state is %s", self._master.state)
        return self._master.state

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._master.output_volume_level(self._output_id)

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._master.output_volume_level(output_id=self._output_id) == 0

    async def async_mute_volume(self, mute):
        """Mute the volume."""
        if mute:
            if self.volume_level == 0:
                return
            self._last_volume = self.volume_level  # store volume level to restore later
            target_volume = 0
        else:
            target_volume = self._last_volume  # restore volume level
        await self.async_set_volume_level(volume=target_volume)

    async def async_set_volume_level(self, volume):
        """Set volume - input range [0,1]."""
        # don't have to multiply by 100 - master function takes care of it
        await self._master.async_set_output_volume_level(
            volume, output_id=self._output_id
        )

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORTED_FEATURES_ZONE


class ForkedDaapdDevice(MediaPlayerDevice):
    """Representation of the main forked-daapd device."""

    @property
    def should_poll(self) -> bool:
        """Entity pushes its state to HA."""
        return False

    async def async_toggle(self):
        """Toggle the power on the device.

        Default media player component method counts idle as off - we consider idle to be on but just not playing.
        """
        if self.state == STATE_OFF:
            await self.async_turn_on()
        else:
            await self.async_turn_off()

    def __init__(self, client_session, ip_address, api_port, **kwargs):
        """Initialize the ForkedDaapd Device."""
        super(ForkedDaapdDevice, self).__init__()
        _LOGGER.debug("%s New ForkedDaapdDevice", ip_address)
        self._api = ForkedDaapdAPI(client_session, ip_address, api_port)
        self._data = ForkedDaapdData()
        self._last_outputs = None  # used for device on/off
        self._last_volume = DEFAULT_VOLUME  # used for mute/unmute
        self._player_status_last_updated = None
        self._zones = []
        self._websocket_handler = None

    async def async_init(self):
        """Help to finish initialization with async methods."""
        await self._update(["queue", "config", "outputs", "player"], first_run=True)
        for output in self._data.outputs:
            self._zones.append(ForkedDaapdZone(self, output))
        return [self] + self._zones

    async def async_added_to_hass(self):
        """Use lifecycle hooks."""
        self._websocket_handler = asyncio.create_task(
            self._api.start_websocket_handler(
                self._data.server_config["websocket_port"],
                WS_NOTIFY_EVENT_TYPES,
                self.update_callback,
                WEBSOCKET_RECONNECT_TIME,
            )
        )

    async def _update(self, update_types, first_run=False):
        """Private update method.

        Doesn't update state on first run because entity not available yet.
        """

        def intersect(list1, list2):  # local helper
            intersection = [i for i in list1 + list2 if i in list1 and i in list2]
            return bool(intersection)

        _LOGGER.debug("Updating %s", update_types)
        futures = []
        if intersect(["player", "options", "volume"], update_types):  # update player
            futures.append(self._update_player_status())
        if "config" in update_types:
            futures.append(self._update_server_config())
        if intersect(["outputs", "volume"], update_types):  # update outputs
            futures.append(self._update_outputs(first_run))
        if "queue" in update_types:  # update queue
            futures.append(self._update_queue())
        await asyncio.gather(*futures)
        if intersect(["database", "update"], update_types):  # not supported
            _LOGGER.debug(
                "database/update notifications neither requested nor supported"
            )
        if intersect(
            ["player", "queue"], update_types
        ):  # get track info depends on both of these
            await self._update_track_info()
        if not first_run:
            self.async_schedule_update_ha_state()

    async def _update_player_status(self):
        self._data.player_status = await self._api.get_request("player")
        self._player_status_last_updated = utcnow()

    async def _update_server_config(self):
        self._data.server_config = await self._api.get_request("config")

    async def _update_outputs(self, first_run):
        self._data.outputs = (await self._api.get_request("outputs"))["outputs"]
        if not first_run:
            for output in self._zones:
                output.async_schedule_update_ha_state()

    async def _update_queue(self):
        self._data.queue = await self._api.get_request("queue")

    async def _update_track_info(self):
        try:
            track_id = [
                track["track_id"]
                for track in self._data.queue["items"]
                if track["id"] == self._data.player_status["item_id"]
            ][0]
            self._data.track_info = await self._api.get_track_info(track_id)
        except (IndexError, TypeError):
            _LOGGER.debug("Could not get track_id")
            self._data.track_info = defaultdict(str)

    update_callback = partialmethod(_update)

    async def async_will_remove_from_hass(self):
        """Use lifecycle hook."""
        self._websocket_handler.cancel()

    # for ForkedDaapdZone use
    async def turn_on_output(self, output_id):
        """Enable the output."""
        await self._api.change_output(output_id, selected=True)

    # for ForkedDaapdZone use
    async def turn_off_output(self, output_id):
        """Disable the output."""
        await self._api.change_output(output_id, selected=False)

    # for ForkedDaapdZone use
    def get_selected(self):
        """Return enabled outputs."""
        return [output["id"] for output in self._data.outputs if output["selected"]]

    # for ForkedDaapdZone use
    def output_volume_level(self, output_id):
        """Return output volume level."""
        try:
            return [
                output["volume"]
                for output in self._data.outputs
                if output["id"] == output_id
            ][0] / 100
        except IndexError:
            _LOGGER.error("Output %s not found.", output_id)

    # for ForkedDaapdZone use
    async def async_set_output_volume_level(self, volume, output_id):
        """Set volume - input range [0,1]."""
        await self._api.set_volume(volume=int(volume * 100), output_id=output_id)

    async def async_turn_on(self):
        """Restore the last on outputs state."""
        # restore state
        if self._last_outputs:
            futures = []
            for output in self._last_outputs:
                futures.append(
                    self._api.change_output(
                        output["id"],
                        selected=output["selected"],
                        volume=output["volume"],
                    )
                )
            await asyncio.gather(*futures)
        else:
            selected = []
            for output in self._data.outputs:
                selected.append(output["id"])
            await self._api.set_enabled_outputs(selected)

    async def async_turn_off(self):
        """Pause player and store outputs state."""
        await self._api.pause_playback()
        if any(
            [output["selected"] for output in self._data.outputs]
        ):  # only store output state if some output is selected
            self._last_outputs = self._data.outputs
            await self._api.set_enabled_outputs([])

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self._data.name}"

    @property
    def state(self):
        """State of the player."""
        if self._data.player_status["state"] == "play":
            return STATE_PLAYING
        if all([output["selected"] is False for output in self._data.outputs]):
            return STATE_OFF  # off is any state when it's not playing and all outputs are disabled
        if self._data.player_status["state"] == "pause":
            return STATE_PAUSED
        if (
            self._data.player_status["state"] == "stop"
        ):  # this should catch all remaining cases
            return STATE_IDLE
        _LOGGER.error("Unable to determine player state.")

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._data.player_status["volume"] / 100

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._data.player_status["volume"] == 0

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self._data.player_status["item_id"]

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return self._data.track_info["media_kind"]

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._data.player_status["item_length_ms"] / 1000

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        return self._data.player_status["item_progress_ms"] / 1000

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self._player_status_last_updated

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._data.track_info["title"]

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._data.track_info["artist"]

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self._data.track_info["album"]

    @property
    def media_album_artist(self):
        """Album artist of current playing media, music track only."""
        return self._data.track_info["album_artist"]

    @property
    def media_track(self):
        """Track number of current playing media, music track only."""
        return self._data.track_info["track_number"]

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return self._data.player_status["shuffle"]

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORTED_FEATURES

    async def async_mute_volume(self, mute):
        """Mute the volume."""
        if mute:
            if self.volume_level == 0:
                return
            self._last_volume = self.volume_level  # store volume level to restore later
            target_volume = 0
        else:
            target_volume = self._last_volume  # restore volume level
        await self._api.set_volume(volume=int(target_volume * 100))

    async def async_set_volume_level(self, volume):
        """Set volume - input range [0,1]."""
        await self._api.set_volume(volume=int(volume * 100))

    async def async_media_play(self):
        """Start playback."""
        await self._api.start_playback()

    async def async_media_pause(self):
        """Pause playback."""
        await self._api.pause_playback()

    async def async_media_stop(self):
        """Stop playback."""
        await self._api.stop_playback()

    async def async_media_previous_track(self):
        """Skip to previous track."""
        await self._api.previous_track()

    async def async_media_next_track(self):
        """Skip to next track."""
        await self._api.next_track()

    async def async_media_seek(self, position):
        """Seek to position."""
        await self._api.seek(position_ms=int(position * 1000))

    async def async_clear_playlist(self):
        """Clear playlist."""
        await self._api.clear_playlist()

    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        await self._api.shuffle(shuffle)
