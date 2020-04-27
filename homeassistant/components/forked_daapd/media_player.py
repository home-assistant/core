"""This library brings support for forked_daapd to Home Assistant."""
import asyncio
from collections import defaultdict
import logging

from pyforked_daapd import ForkedDaapdAPI
from pylibrespot_java import LibrespotJavaAPI

from homeassistant.components.media_player import MediaPlayerDevice
from homeassistant.components.media_player.const import MEDIA_TYPE_MUSIC
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.util.dt import utcnow

from .const import (
    CONF_PIPE_CONTROL,
    CONF_PIPE_CONTROL_PORT,
    CONF_TTS_PAUSE_TIME,
    CONF_TTS_VOLUME,
    DEFAULT_TTS_PAUSE_TIME,
    DEFAULT_TTS_VOLUME,
    DEFAULT_UNMUTE_VOLUME,
    DOMAIN,
    FD_NAME,
    HASS_DATA_OUTPUTS_KEY,
    HASS_DATA_REMOVE_LISTENERS_KEY,
    HASS_DATA_UPDATER_KEY,
    SERVER_UNIQUE_ID,
    SIGNAL_ADD_ZONES,
    SIGNAL_CONFIG_OPTIONS_UPDATE,
    SIGNAL_UPDATE_MASTER,
    SIGNAL_UPDATE_OUTPUTS,
    SIGNAL_UPDATE_PLAYER,
    SIGNAL_UPDATE_QUEUE,
    STARTUP_DATA,
    SUPPORTED_FEATURES,
    SUPPORTED_FEATURES_ZONE,
    TTS_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

WS_NOTIFY_EVENT_TYPES = ["player", "outputs", "volume", "options", "queue"]
WEBSOCKET_RECONNECT_TIME = 30  # seconds


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up forked-daapd from a config entry."""
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    password = config_entry.data[CONF_PASSWORD]
    forked_daapd_api = ForkedDaapdAPI(
        async_get_clientsession(hass), host, port, password
    )
    forked_daapd_master = ForkedDaapdMaster(
        clientsession=async_get_clientsession(hass),
        api=forked_daapd_api,
        ip_address=host,
        api_port=port,
        api_password=password,
        config_entry=config_entry,
    )

    @callback
    def async_add_zones(api, outputs):
        zone_entities = []
        for output in outputs:
            zone_entities.append(ForkedDaapdZone(api, output))
        async_add_entities(zone_entities, False)

    remove_add_zones_listener = async_dispatcher_connect(
        hass, SIGNAL_ADD_ZONES, async_add_zones
    )
    remove_entry_listener = config_entry.add_update_listener(update_listener)

    hass.data[DOMAIN] = {
        HASS_DATA_REMOVE_LISTENERS_KEY: [
            remove_add_zones_listener,
            remove_entry_listener,
        ],
        HASS_DATA_OUTPUTS_KEY: [],
    }
    async_add_entities([forked_daapd_master], False)
    forked_daapd_updater = ForkedDaapdUpdater(hass, forked_daapd_api)
    await forked_daapd_updater.async_init()
    hass.data[DOMAIN][HASS_DATA_UPDATER_KEY] = forked_daapd_updater


async def update_listener(hass, entry):
    """Handle options update."""
    async_dispatcher_send(hass, SIGNAL_CONFIG_OPTIONS_UPDATE, entry.options)


class ForkedDaapdZone(MediaPlayerDevice):
    """Representation of a forked-daapd output."""

    def __init__(self, api, output):
        """Initialize the ForkedDaapd Zone."""
        self._api = api
        self._output = output
        self._output_id = output["id"]
        self._last_volume = DEFAULT_UNMUTE_VOLUME  # used for mute/unmute
        self._available = False

    async def async_added_to_hass(self):
        """Use lifecycle hooks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_OUTPUTS, self._async_update_output_callback
            )
        )

    @callback
    def _async_update_output_callback(self, outputs):
        new_output = next(
            (output for output in outputs if output["id"] == self._output_id), None
        )
        self._available = bool(new_output)
        if self._available:
            self._output = new_output
        self.async_write_ha_state()

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._output_id

    @property
    def should_poll(self) -> bool:
        """Entity pushes its state to HA."""
        return False

    async def async_toggle(self):
        """Toggle the power on the zone."""
        if self.state == STATE_OFF:
            await self.async_turn_on()
        else:
            await self.async_turn_off()

    @property
    def available(self) -> bool:
        """Return whether the zone is available."""
        return self._available

    async def async_turn_on(self):
        """Enable the output."""
        await self._api.change_output(self._output_id, selected=True)

    async def async_turn_off(self):
        """Disable the output."""
        await self._api.change_output(self._output_id, selected=False)

    @property
    def name(self):
        """Return the name of the zone."""
        return f"{FD_NAME} output ({self._output['name']})"

    @property
    def state(self):
        """State of the zone."""
        if self._output["selected"]:
            return STATE_ON
        return STATE_OFF

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._output["volume"] / 100

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._output["volume"] == 0

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
        await self._api.set_volume(volume=volume * 100, output_id=self._output_id)

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORTED_FEATURES_ZONE


class ForkedDaapdMaster(MediaPlayerDevice):
    """Representation of the main forked-daapd device."""

    def __init__(
        self, clientsession, api, ip_address, api_port, api_password, config_entry
    ):
        """Initialize the ForkedDaapd Master Device."""
        self._api = api
        self._player = STARTUP_DATA[
            "player"
        ]  # _player, _outputs, and _queue are loaded straight from api
        self._outputs = STARTUP_DATA["outputs"]
        self._queue = STARTUP_DATA["queue"]
        self._track_info = defaultdict(
            str
        )  # _track info is found by matching _player data with _queue data
        self._last_outputs = None  # used for device on/off
        self._last_volume = DEFAULT_UNMUTE_VOLUME
        self._player_last_updated = None
        self._pipe_control_api = None
        self._ip_address = (
            ip_address  # need to save this because pipe control is on same ip
        )
        self._tts_pause_time = DEFAULT_TTS_PAUSE_TIME
        self._tts_volume = DEFAULT_TTS_VOLUME
        self._tts_requested = False
        self._tts_queued = False
        self._tts_playing_event = asyncio.Event()
        self._on_remove = None
        self._available = False
        self._clientsession = clientsession
        self._config_entry = config_entry
        self.update_options(config_entry.options)

    async def async_added_to_hass(self):
        """Use lifecycle hooks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_PLAYER, self._update_player
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE_QUEUE, self._update_queue)
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_OUTPUTS, self._update_outputs
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_MASTER, self._update_callback
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_CONFIG_OPTIONS_UPDATE, self.update_options
            )
        )

    @callback
    def _update_callback(self, available):
        """Call update method."""
        self._available = available
        self.async_write_ha_state()

    @callback
    def update_options(self, options):
        """Update forked-daapd server options."""
        if options.get(CONF_PIPE_CONTROL) == "librespot-java":
            self._pipe_control_api = LibrespotJavaAPI(
                self._clientsession, self._ip_address, options[CONF_PIPE_CONTROL_PORT]
            )
        else:
            self._pipe_control_api = None
        if options.get(CONF_TTS_PAUSE_TIME):
            self._tts_pause_time = options[CONF_TTS_PAUSE_TIME]
        if options.get(CONF_TTS_VOLUME):
            self._tts_volume = options[CONF_TTS_VOLUME]

    @callback
    def _update_player(self, player):
        self._player = player
        self._player_last_updated = utcnow()
        self._update_track_info()
        if self._tts_queued:
            self._tts_playing_event.set()
            self._tts_queued = False

    @callback
    def _update_queue(self, queue):
        self._queue = queue
        if (
            self._tts_requested
            and self._queue["count"] == 1
            and self._queue["items"][0]["uri"].find("tts_proxy") != -1
        ):
            self._tts_requested = False
            self._tts_queued = True
        self._update_track_info()

    @callback
    def _update_outputs(self, outputs):
        self._outputs = outputs

    def _update_track_info(self):  # run during every player or queue update
        try:
            self._track_info = next(
                track
                for track in self._queue["items"]
                if track["id"] == self._player["item_id"]
            )
        except (StopIteration, TypeError, KeyError):
            _LOGGER.debug("Could not get track info.")
            self._track_info = defaultdict(str)

    @property
    def unique_id(self):
        """Return unique ID."""
        return SERVER_UNIQUE_ID

    @property
    def should_poll(self) -> bool:
        """Entity pushes its state to HA."""
        return False

    @property
    def available(self) -> bool:
        """Return whether the master is available."""
        return self._available

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
            for output in self._outputs:
                selected.append(output["id"])
            await self._api.set_enabled_outputs(selected)

    async def async_turn_off(self):
        """Pause player and store outputs state."""
        await self.async_media_pause()
        if any(
            [output["selected"] for output in self._outputs]
        ):  # only store output state if some output is selected
            self._last_outputs = self._outputs
            await self._api.set_enabled_outputs([])

    async def async_toggle(self):
        """Toggle the power on the device.

        Default media player component method counts idle as off.
        We consider idle to be on but just not playing.
        """
        if self.state == STATE_OFF:
            await self.async_turn_on()
        else:
            await self.async_turn_off()

    @property
    def name(self):
        """Return the name of the device."""
        return f"{FD_NAME} server"

    @property
    def state(self):
        """State of the player."""
        if self._player["state"] == "play":
            return STATE_PLAYING
        if not any([output["selected"] for output in self._outputs]):
            return STATE_OFF  # off is any state when it's not playing and all outputs are disabled
        if self._player["state"] == "pause":
            return STATE_PAUSED
        if self._player["state"] == "stop":  # this should catch all remaining cases
            return STATE_IDLE

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._player["volume"] / 100

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._player["volume"] == 0

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self._player["item_id"]

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return self._track_info["media_kind"]

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._player["item_length_ms"] / 1000

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        return self._player["item_progress_ms"] / 1000

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self._player_last_updated

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._track_info["title"]

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._track_info["artist"]

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self._track_info["album"]

    @property
    def media_album_artist(self):
        """Album artist of current playing media, music track only."""
        return self._track_info["album_artist"]

    @property
    def media_track(self):
        """Track number of current playing media, music track only."""
        return self._track_info["track_number"]

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return self._player["shuffle"]

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
        url = self._track_info.get("artwork_url")
        if url:
            url = self._api.full_url(url)
        return url

    async def _set_tts_volumes(self):
        if self._outputs:
            futures = []
            for output in self._outputs:
                futures.append(
                    self._api.change_output(
                        output["id"], selected=True, volume=self._tts_volume * 100
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
            saved_song_position = self._player["item_progress_ms"]
            saved_queue = (
                self._queue if self._queue["count"] > 0 else None
            )  # stash queue
            if saved_queue:
                saved_queue_position = next(
                    i
                    for i, item in enumerate(saved_queue["items"])
                    if item["id"] == self._player["item_id"]
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
                    self._queue["items"][0]["length_ms"]
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


class ForkedDaapdUpdater:
    """Manage updates for the forked-daapd device."""

    def __init__(self, hass, api):
        """Initialize."""
        self.hass = hass
        self._api = api
        self.websocket_handler = None
        self._all_output_ids = []

    async def async_init(self):
        """Perform async portion of class initialization."""
        server_config = await self._api.get_request("config")
        websocket_port = server_config.get("websocket_port")
        if websocket_port:
            self.websocket_handler = asyncio.create_task(
                self._api.start_websocket_handler(
                    server_config["websocket_port"],
                    WS_NOTIFY_EVENT_TYPES,
                    self._update,
                    WEBSOCKET_RECONNECT_TIME,
                    self._disconnected_callback,
                )
            )
        else:
            _LOGGER.error("Invalid websocket port.")

    def _disconnected_callback(self):
        async_dispatcher_send(self.hass, SIGNAL_UPDATE_MASTER, False)
        async_dispatcher_send(self.hass, SIGNAL_UPDATE_OUTPUTS, [])

    async def _update(self, update_types):
        """Private update method."""

        def intersect(list1, list2):  # local helper
            intersection = [i for i in list1 + list2 if i in list1 and i in list2]
            return bool(intersection)

        _LOGGER.debug("Updating %s", update_types)
        if "queue" in update_types:  # update queue
            queue = await self._api.get_request("queue")
            async_dispatcher_send(self.hass, SIGNAL_UPDATE_QUEUE, queue)
            await self.hass.async_block_till_done()  # make sure queue done before player for async_play_media
        # order of below don't matter
        if intersect(["player", "options", "volume"], update_types):  # update player
            player = await self._api.get_request("player")
            async_dispatcher_send(self.hass, SIGNAL_UPDATE_PLAYER, player)
        if intersect(["outputs", "volume"], update_types):  # update outputs
            outputs = (await self._api.get_request("outputs"))["outputs"]
            await self._add_zones(outputs)
            async_dispatcher_send(self.hass, SIGNAL_UPDATE_OUTPUTS, outputs)
        if intersect(["database", "update", "config"], update_types):  # not supported
            _LOGGER.debug(
                "database/update notifications neither requested nor supported"
            )
        await self.hass.async_block_till_done()  # make sure callbacks done before requesting state update
        async_dispatcher_send(self.hass, SIGNAL_UPDATE_MASTER, True)

    async def _add_zones(self, outputs):
        outputs_to_add = []
        for output in outputs:
            if output["id"] not in self._all_output_ids:
                self._all_output_ids.append(output["id"])
                outputs_to_add.append(output)
        if outputs_to_add:
            async_dispatcher_send(
                self.hass, SIGNAL_ADD_ZONES, self._api, outputs_to_add
            )
            await self.hass.async_block_till_done()  # make sure all zones are added before returning
