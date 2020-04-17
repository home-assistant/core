"""This library brings support for forked_daapd to Home Assistant."""
import asyncio
from collections import defaultdict
from functools import partialmethod
import logging

from pyforked_daapd import ForkedDaapdAPI, ForkedDaapdData
from pylibrespot_java import LibrespotJavaAPI

from homeassistant.components.media_player import MediaPlayerDevice
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
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
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.dt import utcnow

from .const import (
    CONF_DEFAULT_VOLUME,
    CONF_PIPE_CONTROL,
    CONF_PIPE_CONTROL_PORT,
    CONF_TTS_PAUSE_TIME,
    CONF_TTS_VOLUME,
    DEFAULT_TTS_PAUSE_TIME,
    DEFAULT_TTS_VOLUME,
    DOMAIN,
    FD_NAME,
    SERVER_UNIQUE_ID,
    TTS_TIMEOUT,
)

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
    | SUPPORT_PLAY_MEDIA
)

SUPPORTED_FEATURES_ZONE = (
    SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF
)

WS_NOTIFY_EVENT_TYPES = ["player", "outputs", "volume", "options", "queue"]
WEBSOCKET_RECONNECT_TIME = 30  # seconds
# device manufacturer model area integration battery


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up forked-daapd from a config entry."""
    if not hass.data.get(DOMAIN):  # only set up if not already set up
        await _async_setup_platform(
            hass, config=config_entry.data, async_add_entities=async_add_entities
        )
        await update_listener(hass, config_entry)
        config_entry.add_update_listener(update_listener)


async def update_listener(hass, entry):
    """Handle options update."""
    hass.data[DOMAIN].update_options(entry.options)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the forked-daapd platform.

    Deprecated.
    """
    _LOGGER.warning(
        "Setting configuration for forked-daapd via platform is deprecated. "
        "Configure via the forked-daapd integration instead."
    )
    await _async_setup_platform(hass, config, async_add_entities, discovery_info)


async def _async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the forked-daapd platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    password = config.get(CONF_PASSWORD)
    default_volume = config.get(CONF_DEFAULT_VOLUME)
    forked_daapd_device = ForkedDaapdDevice(
        hass=hass,
        name=name,
        ip_address=host,
        api_port=port,
        api_password=password,
        default_volume=default_volume,
        async_add_entities=async_add_entities,
    )
    await forked_daapd_device.async_init()  # updates essential info and adds entities
    hass.data[DOMAIN] = forked_daapd_device


class ForkedDaapdZone(MediaPlayerDevice):
    """Representation of a forked-daapd output."""

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._output_id

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

    def __init__(self, master_device, output, default_volume):
        """Initialize the ForkedDaapd Zone."""
        super(ForkedDaapdZone, self).__init__()
        _LOGGER.debug("New ForkedDaapdZone")
        self._master = master_device
        self._name = output["name"]
        self._type = output["type"]
        self._output_id = output["id"]
        self._last_volume = (
            output["volume"] if output["volume"] else default_volume
        )  # used for mute/unmute
        self._available = True

    @property
    def available(self) -> bool:
        """Return whether the zone is available."""
        return self._available

    @available.setter
    def available(self, val):
        """Setter for property."""
        self._available = val

    async def async_turn_on(self):
        """Enable the output."""
        await self._master.turn_on_output(self._output_id)

    async def async_turn_off(self):
        """Disable the output."""
        await self._master.turn_off_output(self._output_id)

    @property
    def name(self):
        """Return the name of the zone."""
        return f"{FD_NAME} output ({self._name})"

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

    def __init__(
        self,
        hass,
        name,
        ip_address,
        api_port,
        api_password,
        default_volume,
        async_add_entities,
    ):
        """Initialize the ForkedDaapd Device."""
        super(ForkedDaapdDevice, self).__init__()
        _LOGGER.debug("%s New ForkedDaapdDevice", ip_address)
        self.hass = hass
        self._api = ForkedDaapdAPI(
            async_get_clientsession(hass), ip_address, api_port, api_password
        )
        self._data = ForkedDaapdData()
        self._last_outputs = None  # used for device on/off
        self._default_volume = default_volume  # used for mute/unmute
        self._last_volume = None
        self._player_last_updated = None
        self._zones = {}
        self._websocket_handler = None
        self._pipe_control_api = None
        self._name = name
        self._ip_address = ip_address
        self._api_port = api_port
        self._api_password = api_password
        self._tts_pause_time = DEFAULT_TTS_PAUSE_TIME
        self._tts_volume = DEFAULT_TTS_VOLUME
        self._tts_requested = False
        self._tts_queued = False
        self._tts_playing_event = asyncio.Event()
        self._async_add_entities = async_add_entities  # use to add zones

    async def async_init(self):
        """Help to finish initialization with async methods."""
        await self._update_server_config()
        await self._update_player()
        await self._update_outputs()  # adds zones
        self._async_add_entities(
            [self], False
        )  # Will update state later on update callback

    async def async_added_to_hass(self):
        """Use lifecycle hooks."""
        await self._update_server_config()  # get websocket port
        self._websocket_handler = asyncio.create_task(
            self._api.start_websocket_handler(
                self._data.server_config["websocket_port"],
                WS_NOTIFY_EVENT_TYPES,
                self.update_callback,
                WEBSOCKET_RECONNECT_TIME,
            )
        )

    async def async_will_remove_from_hass(self):
        """Use lifecycle hook."""
        self._websocket_handler.cancel()
        del self.hass.data[DOMAIN]

    @callback
    def update_options(self, options):
        """Update forked-daapd server options."""
        if options.get(CONF_PIPE_CONTROL) == "librespot-java":
            self._pipe_control_api = LibrespotJavaAPI(
                async_get_clientsession(self.hass),
                self._ip_address,
                options[CONF_PIPE_CONTROL_PORT],
            )
        else:
            self._pipe_control_api = None
        if options.get(CONF_TTS_PAUSE_TIME):
            self._tts_pause_time = options[CONF_TTS_PAUSE_TIME]
        if options.get(CONF_TTS_VOLUME):
            self._tts_volume = options[CONF_TTS_VOLUME]

    @property
    def unique_id(self):
        """Return unique ID."""
        return SERVER_UNIQUE_ID

    @property
    def should_poll(self) -> bool:
        """Entity pushes its state to HA."""
        return False

    async def _update(self, update_types, first_run=False):
        """Private update method.

        Doesn't update state on first run because entity not available yet.
        """

        def intersect(list1, list2):  # local helper
            intersection = [i for i in list1 + list2 if i in list1 and i in list2]
            return bool(intersection)

        _LOGGER.debug("Updating %s", update_types)
        if "queue" in update_types:  # update queue
            await self._update_queue()  # need to run queue before player for tts, so run first
        # order of below don't matter
        if intersect(["player", "options", "volume"], update_types):  # update player
            await self._update_player()
        if intersect(["outputs", "volume"], update_types):  # update outputs
            await self._update_outputs()
            self._update_zones()
        if intersect(["database", "update", "config"], update_types):  # not supported
            _LOGGER.debug(
                "database/update notifications neither requested nor supported"
            )
        self.async_schedule_update_ha_state()

    async def _update_server_config(self):
        self._data.server_config = await self._api.get_request("config")

    async def _update_player(self):
        self._data.player = await self._api.get_request("player")
        self._player_last_updated = utcnow()
        self._update_track_info()
        if self._tts_queued:
            self._tts_playing_event.set()
            self._tts_queued = False

    async def _update_outputs(self):
        self._data.outputs = (await self._api.get_request("outputs"))["outputs"]
        for output in self._data.outputs:
            if output["id"] not in self._zones:
                self._zones[output["id"]] = ForkedDaapdZone(
                    self, output, self._default_volume
                )
                self._async_add_entities([self._zones[output["id"]]], False)

    def _update_zones(self):
        for output_id, zone in self._zones.items():
            zone.available = output_id in [
                output["id"] for output in self._data.outputs
            ]  # mark which zones are available
            zone.async_schedule_update_ha_state()

    async def _update_queue(self):
        self._data.queue = await self._api.get_request("queue")
        if (
            self._tts_requested
            and self._data.queue["count"] == 1
            and self._data.queue["items"][0]["uri"].find("tts_proxy") != -1
        ):
            self._tts_requested = False
            self._tts_queued = True
        self._update_track_info()

    def _update_track_info(self):  # run after every player or queue update
        try:
            self._data.track_info = next(
                track
                for track in self._data.queue["items"]
                if track["id"] == self._data.player["item_id"]
            )
        except (StopIteration, TypeError, KeyError):
            _LOGGER.debug("Could not get track info.")
            self._data.track_info = defaultdict(str)

    update_callback = partialmethod(_update)

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
            _LOGGER.warning("Output %s not found.", output_id)

    # for ForkedDaapdZone use
    async def async_set_output_volume_level(self, volume, output_id):
        """Set volume - input range [0,1]."""
        await self._api.set_volume(volume=volume * 100, output_id=output_id)

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
            await asyncio.wait(futures)
        else:
            selected = []
            for output in self._data.outputs:
                selected.append(output["id"])
            await self._api.set_enabled_outputs(selected)

    async def async_turn_off(self):
        """Pause player and store outputs state."""
        await self.async_media_pause()
        if any(
            [output["selected"] for output in self._data.outputs]
        ):  # only store output state if some output is selected
            self._last_outputs = self._data.outputs
            await self._api.set_enabled_outputs([])

    async def async_toggle(self):
        """Toggle the power on the device.

        Default media player component method counts idle as off - we consider idle to be on but just not playing.
        """
        if self.state == STATE_OFF:
            await self.async_turn_on()
        else:
            await self.async_turn_off()

    @property
    def name(self):
        """Return the name of the device."""
        return f"{FD_NAME} server ({self._name})"

    @property
    def state(self):
        """State of the player."""
        if self._data.player["state"] == "play":
            return STATE_PLAYING
        if all([output.get("selected") is False for output in self._data.outputs]):
            return STATE_OFF  # off is any state when it's not playing and all outputs are disabled
        if self._data.player["state"] == "pause":
            return STATE_PAUSED
        if (
            self._data.player["state"] == "stop"
        ):  # this should catch all remaining cases
            return STATE_IDLE
        _LOGGER.warning("Unable to determine player state.")

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._data.player["volume"] / 100

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._data.player["volume"] == 0

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self._data.player["item_id"]

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return self._data.track_info["media_kind"]

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._data.player["item_length_ms"] / 1000

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        return self._data.player["item_progress_ms"] / 1000

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self._player_last_updated

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
        return self._data.player["shuffle"]

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
            target_volume = (
                self._last_volume if self._last_volume else self._default_volume
            )  # restore volume level
        await self._api.set_volume(volume=target_volume * 100)

    async def async_set_volume_level(self, volume):
        """Set volume - input range [0,1]."""
        await self._api.set_volume(volume=volume * 100)

    async def async_media_play(self):
        """Start playback."""
        if self._pipe_control_api:
            await self._pipe_control_api.player_resume()
        else:
            await self._api.start_playback()

    async def async_media_pause(self):
        """Pause playback."""
        if self._pipe_control_api:
            await self._pipe_control_api.player_pause()
        else:
            await self._api.pause_playback()

    async def async_media_stop(self):
        """Stop playback."""
        await self._api.stop_playback()

    async def async_media_previous_track(self):
        """Skip to previous track."""
        if self._pipe_control_api:
            await self._pipe_control_api.player_prev()
        else:
            await self._api.previous_track()

    async def async_media_next_track(self):
        """Skip to next track."""
        if self._pipe_control_api:
            await self._pipe_control_api.player_next()
        else:
            await self._api.next_track()

    async def async_media_seek(self, position):
        """Seek to position."""
        await self._api.seek(position_ms=position * 1000)

    async def async_clear_playlist(self):
        """Clear playlist."""
        await self._api.clear_queue()

    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        await self._api.shuffle(shuffle)

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        creds = f"admin:{self._api_password}@" if self._api_password else ""
        url = self._data.track_info.get("artwork_url")
        if url:
            url = f"http://{creds}{self._ip_address}:{self._api_port}{url}"
        return url

    async def _set_tts_volumes(self):
        futures = []
        for output in self._data.outputs:
            futures.append(
                self._api.change_output(
                    output["id"], selected=True, volume=self._tts_volume * 100,
                )
            )
        await asyncio.wait(futures)
        await self._api.set_volume(volume=self._tts_volume * 100)

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play a URI."""
        if media_type == MEDIA_TYPE_MUSIC:
            saved_state = self.state  # save play state
            await self.async_turn_off()  # pauses and saves output states
            await self._set_tts_volumes()
            await asyncio.sleep(self._tts_pause_time)
            # save position
            saved_song_position = self._data.player["item_progress_ms"]
            saved_queue = (
                self._data.queue if self._data.queue["count"] > 0 else None
            )  # stash queue
            if saved_queue:
                saved_queue_position = next(
                    i
                    for i, item in enumerate(saved_queue["items"])
                    if item["id"] == self._data.player["item_id"]
                )
                await self._api.clear_queue()
            self._tts_requested = True
            await self._api.add_to_queue(uris=media_id, playback="start")
            try:
                await asyncio.wait_for(
                    self._tts_playing_event.wait(), timeout=TTS_TIMEOUT
                )
                # we have started TTS, now wait for completion
                await asyncio.sleep(
                    self._data.queue["items"][0]["length_ms"]
                    / 1000  # player may not have updated yet so grab length from queue
                    + self._tts_pause_time
                )
            except asyncio.TimeoutError:
                self._tts_requested = False
                _LOGGER.warning("TTS request timed out.")
            self._tts_playing_event.clear()
            # TTS done, return to normal
            await self.async_turn_on()  # restores outputs
            await self._api.clear_queue()
            if self._pipe_control_api:  # resume pipe
                if saved_state == STATE_PLAYING:
                    await self.async_media_play()
            else:  # restore stashed queue
                if saved_queue:
                    uris = ""
                    for item in saved_queue["items"]:
                        uris += item["uri"] + ","
                    await self._api.add_to_queue(
                        uris=uris,
                        playback="start",
                        playback_from_position=saved_queue_position,
                    )
                    await self._api.seek(position_ms=saved_song_position)
                    if saved_state != STATE_PLAYING:
                        await self.async_media_pause()
        else:
            _LOGGER.debug("Media type '%s' not supported.", media_type)
