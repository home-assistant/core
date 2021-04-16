"""This library brings support for forked_daapd to Home Assistant."""
import asyncio
from collections import defaultdict
import logging

from pyforked_daapd import ForkedDaapdAPI
from pylibrespot_java import LibrespotJavaAPI

from homeassistant.components.media_player import MediaPlayerEntity
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
    CALLBACK_TIMEOUT,
    CONF_LIBRESPOT_JAVA_PORT,
    CONF_MAX_PLAYLISTS,
    CONF_TTS_PAUSE_TIME,
    CONF_TTS_VOLUME,
    DEFAULT_TTS_PAUSE_TIME,
    DEFAULT_TTS_VOLUME,
    DEFAULT_UNMUTE_VOLUME,
    DOMAIN,
    FD_NAME,
    HASS_DATA_REMOVE_LISTENERS_KEY,
    HASS_DATA_UPDATER_KEY,
    KNOWN_PIPES,
    PIPE_FUNCTION_MAP,
    SIGNAL_ADD_ZONES,
    SIGNAL_CONFIG_OPTIONS_UPDATE,
    SIGNAL_UPDATE_DATABASE,
    SIGNAL_UPDATE_MASTER,
    SIGNAL_UPDATE_OUTPUTS,
    SIGNAL_UPDATE_PLAYER,
    SIGNAL_UPDATE_QUEUE,
    SOURCE_NAME_CLEAR,
    SOURCE_NAME_DEFAULT,
    STARTUP_DATA,
    SUPPORTED_FEATURES,
    SUPPORTED_FEATURES_ZONE,
    TTS_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

WS_NOTIFY_EVENT_TYPES = ["player", "outputs", "volume", "options", "queue", "database"]
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
            zone_entities.append(ForkedDaapdZone(api, output, config_entry.entry_id))
        async_add_entities(zone_entities, False)

    remove_add_zones_listener = async_dispatcher_connect(
        hass, SIGNAL_ADD_ZONES.format(config_entry.entry_id), async_add_zones
    )
    remove_entry_listener = config_entry.add_update_listener(update_listener)

    if not hass.data.get(DOMAIN):
        hass.data[DOMAIN] = {config_entry.entry_id: {}}
    hass.data[DOMAIN][config_entry.entry_id] = {
        HASS_DATA_REMOVE_LISTENERS_KEY: [
            remove_add_zones_listener,
            remove_entry_listener,
        ]
    }
    async_add_entities([forked_daapd_master], False)
    forked_daapd_updater = ForkedDaapdUpdater(
        hass, forked_daapd_api, config_entry.entry_id
    )
    await forked_daapd_updater.async_init()
    hass.data[DOMAIN][config_entry.entry_id][
        HASS_DATA_UPDATER_KEY
    ] = forked_daapd_updater


async def update_listener(hass, entry):
    """Handle options update."""
    async_dispatcher_send(
        hass, SIGNAL_CONFIG_OPTIONS_UPDATE.format(entry.entry_id), entry.options
    )


class ForkedDaapdZone(MediaPlayerEntity):
    """Representation of a forked-daapd output."""

    def __init__(self, api, output, entry_id):
        """Initialize the ForkedDaapd Zone."""
        self._api = api
        self._output = output
        self._output_id = output["id"]
        self._last_volume = DEFAULT_UNMUTE_VOLUME  # used for mute/unmute
        self._available = True
        self._entry_id = entry_id

    async def async_added_to_hass(self):
        """Use lifecycle hooks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE_OUTPUTS.format(self._entry_id),
                self._async_update_output_callback,
            )
        )

    @callback
    def _async_update_output_callback(self, outputs, _event=None):
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
        return f"{self._entry_id}-{self._output_id}"

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


class ForkedDaapdMaster(MediaPlayerEntity):
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
        self._last_outputs = []  # used for device on/off
        self._last_volume = DEFAULT_UNMUTE_VOLUME
        self._player_last_updated = None
        self._pipe_control_api = {}
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
        self._paused_event = asyncio.Event()
        self._pause_requested = False
        self._sources_uris = {}
        self._source = SOURCE_NAME_DEFAULT
        self._max_playlists = None

    async def async_added_to_hass(self):
        """Use lifecycle hooks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE_PLAYER.format(self._config_entry.entry_id),
                self._update_player,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE_QUEUE.format(self._config_entry.entry_id),
                self._update_queue,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE_OUTPUTS.format(self._config_entry.entry_id),
                self._update_outputs,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE_MASTER.format(self._config_entry.entry_id),
                self._update_callback,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_CONFIG_OPTIONS_UPDATE.format(self._config_entry.entry_id),
                self.update_options,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE_DATABASE.format(self._config_entry.entry_id),
                self._update_database,
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
        if CONF_LIBRESPOT_JAVA_PORT in options:
            self._pipe_control_api["librespot-java"] = LibrespotJavaAPI(
                self._clientsession, self._ip_address, options[CONF_LIBRESPOT_JAVA_PORT]
            )
        if CONF_TTS_PAUSE_TIME in options:
            self._tts_pause_time = options[CONF_TTS_PAUSE_TIME]
        if CONF_TTS_VOLUME in options:
            self._tts_volume = options[CONF_TTS_VOLUME]
        if CONF_MAX_PLAYLISTS in options:
            # sources not updated until next _update_database call
            self._max_playlists = options[CONF_MAX_PLAYLISTS]

    @callback
    def _update_player(self, player, event):
        self._player = player
        self._player_last_updated = utcnow()
        self._update_track_info()
        if self._tts_queued:
            self._tts_playing_event.set()
            self._tts_queued = False
        if self._pause_requested:
            self._paused_event.set()
            self._pause_requested = False
        event.set()

    @callback
    def _update_queue(self, queue, event):
        self._queue = queue
        if (
            self._tts_requested
            and self._queue["count"] == 1
            and self._queue["items"][0]["uri"].find("tts_proxy") != -1
        ):
            self._tts_requested = False
            self._tts_queued = True

        if (
            self._queue["count"] >= 1
            and self._queue["items"][0]["data_kind"] == "pipe"
            and self._queue["items"][0]["title"] in KNOWN_PIPES
        ):  # if we're playing a pipe, set the source automatically so we can forward controls
            self._source = f"{self._queue['items'][0]['title']} (pipe)"
        self._update_track_info()
        event.set()

    @callback
    def _update_outputs(self, outputs, event=None):
        if event:  # Calling without event is meant for zone, so ignore
            self._outputs = outputs
            event.set()

    @callback
    def _update_database(self, pipes, playlists, event):
        self._sources_uris = {SOURCE_NAME_CLEAR: None, SOURCE_NAME_DEFAULT: None}
        if pipes:
            self._sources_uris.update(
                {
                    f"{pipe['title']} (pipe)": pipe["uri"]
                    for pipe in pipes
                    if pipe["title"] in KNOWN_PIPES
                }
            )
        if playlists:
            self._sources_uris.update(
                {
                    f"{playlist['name']} (playlist)": playlist["uri"]
                    for playlist in playlists[: self._max_playlists]
                }
            )
        event.set()

    def _update_track_info(self):  # run during every player or queue update
        try:
            self._track_info = next(
                track
                for track in self._queue["items"]
                if track["id"] == self._player["item_id"]
            )
        except (StopIteration, TypeError, KeyError):
            _LOGGER.debug("Could not get track info")
            self._track_info = defaultdict(str)

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._config_entry.entry_id

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
        await self._api.set_volume(volume=self._last_volume * 100)
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
        else:  # enable all outputs
            await self._api.set_enabled_outputs(
                [output["id"] for output in self._outputs]
            )

    async def async_turn_off(self):
        """Pause player and store outputs state."""
        await self.async_media_pause()
        self._last_outputs = self._outputs
        if any(output["selected"] for output in self._outputs):
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
        if self._player["state"] == "pause":
            return STATE_PAUSED
        if not any(output["selected"] for output in self._outputs):
            return STATE_OFF
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
        # Use album field when data_kind is url
        # https://github.com/ejurgensen/forked-daapd/issues/351
        if self._track_info["data_kind"] == "url":
            return self._track_info["album"]
        return self._track_info["title"]

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._track_info["artist"]

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        # Use title field when data_kind is url
        # https://github.com/ejurgensen/forked-daapd/issues/351
        if self._track_info["data_kind"] == "url":
            return self._track_info["title"]
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

    @property
    def source(self):
        """Name of the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return [*self._sources_uris]

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
        if self._use_pipe_control():
            await self._pipe_call(self._use_pipe_control(), "async_media_play")
        else:
            await self._api.start_playback()

    async def async_media_pause(self):
        """Pause playback."""
        if self._use_pipe_control():
            await self._pipe_call(self._use_pipe_control(), "async_media_pause")
        else:
            await self._api.pause_playback()

    async def async_media_stop(self):
        """Stop playback."""
        if self._use_pipe_control():
            await self._pipe_call(self._use_pipe_control(), "async_media_stop")
        else:
            await self._api.stop_playback()

    async def async_media_previous_track(self):
        """Skip to previous track."""
        if self._use_pipe_control():
            await self._pipe_call(
                self._use_pipe_control(), "async_media_previous_track"
            )
        else:
            await self._api.previous_track()

    async def async_media_next_track(self):
        """Skip to next track."""
        if self._use_pipe_control():
            await self._pipe_call(self._use_pipe_control(), "async_media_next_track")
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

    async def _save_and_set_tts_volumes(self):
        if self.volume_level:  # save master volume
            self._last_volume = self.volume_level
        self._last_outputs = self._outputs
        if self._outputs:
            await self._api.set_volume(volume=self._tts_volume * 100)
            futures = []
            for output in self._outputs:
                futures.append(
                    self._api.change_output(
                        output["id"], selected=True, volume=self._tts_volume * 100
                    )
                )
            await asyncio.wait(futures)

    async def _pause_and_wait_for_callback(self):
        """Send pause and wait for the pause callback to be received."""
        self._pause_requested = True
        await self.async_media_pause()
        try:
            await asyncio.wait_for(
                self._paused_event.wait(), timeout=CALLBACK_TIMEOUT
            )  # wait for paused
        except asyncio.TimeoutError:
            self._pause_requested = False
        self._paused_event.clear()

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play a URI."""
        if media_type == MEDIA_TYPE_MUSIC:
            saved_state = self.state  # save play state
            saved_mute = self.is_volume_muted
            sleep_future = asyncio.create_task(
                asyncio.sleep(self._tts_pause_time)
            )  # start timing now, but not exact because of fd buffer + tts latency
            await self._pause_and_wait_for_callback()
            await self._save_and_set_tts_volumes()
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
            self._tts_requested = True
            await sleep_future
            await self._api.add_to_queue(uris=media_id, playback="start", clear=True)
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
                _LOGGER.warning("TTS request timed out")
            self._tts_playing_event.clear()
            # TTS done, return to normal
            await self.async_turn_on()  # restore outputs and volumes
            if saved_mute:  # mute if we were muted
                await self.async_mute_volume(True)
            if self._use_pipe_control():  # resume pipe
                await self._api.add_to_queue(
                    uris=self._sources_uris[self._source], clear=True
                )
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
                        clear=True,
                    )
                    await self._api.seek(position_ms=saved_song_position)
                    if saved_state == STATE_PAUSED:
                        await self.async_media_pause()
                    elif saved_state != STATE_PLAYING:
                        await self.async_media_stop()
        else:
            _LOGGER.debug("Media type '%s' not supported", media_type)

    async def async_select_source(self, source):
        """Change source.

        Source name reflects whether in default mode or pipe mode.
        Selecting playlists/clear sets the playlists/clears but ends up in default mode.
        """
        if source == self._source:
            return

        if self._use_pipe_control():  # if pipe was playing, we need to stop it first
            await self._pause_and_wait_for_callback()
        self._source = source
        if not self._use_pipe_control():  # playlist or clear ends up at default
            self._source = SOURCE_NAME_DEFAULT
        if self._sources_uris.get(source):  # load uris for pipes or playlists
            await self._api.add_to_queue(uris=self._sources_uris[source], clear=True)
        elif source == SOURCE_NAME_CLEAR:  # clear playlist
            await self._api.clear_queue()
        self.async_write_ha_state()

    def _use_pipe_control(self):
        """Return which pipe control from KNOWN_PIPES to use."""
        if self._source[-7:] == " (pipe)":
            return self._source[:-7]
        return ""

    async def _pipe_call(self, pipe_name, base_function_name):
        if self._pipe_control_api.get(pipe_name):
            return await getattr(
                self._pipe_control_api[pipe_name],
                PIPE_FUNCTION_MAP[pipe_name][base_function_name],
            )()
        _LOGGER.warning("No pipe control available for %s", pipe_name)


class ForkedDaapdUpdater:
    """Manage updates for the forked-daapd device."""

    def __init__(self, hass, api, entry_id):
        """Initialize."""
        self.hass = hass
        self._api = api
        self.websocket_handler = None
        self._all_output_ids = set()
        self._entry_id = entry_id

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
            _LOGGER.error("Invalid websocket port")

    def _disconnected_callback(self):
        async_dispatcher_send(
            self.hass, SIGNAL_UPDATE_MASTER.format(self._entry_id), False
        )
        async_dispatcher_send(
            self.hass, SIGNAL_UPDATE_OUTPUTS.format(self._entry_id), []
        )

    async def _update(self, update_types):
        """Private update method."""
        update_types = set(update_types)
        update_events = {}
        _LOGGER.debug("Updating %s", update_types)
        if (
            "queue" in update_types
        ):  # update queue, queue before player for async_play_media
            queue = await self._api.get_request("queue")
            if queue:
                update_events["queue"] = asyncio.Event()
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_UPDATE_QUEUE.format(self._entry_id),
                    queue,
                    update_events["queue"],
                )
        # order of below don't matter
        if not {"outputs", "volume"}.isdisjoint(update_types):  # update outputs
            outputs = await self._api.get_request("outputs")
            if outputs:
                outputs = outputs["outputs"]
                update_events[
                    "outputs"
                ] = asyncio.Event()  # only for master, zones should ignore
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_UPDATE_OUTPUTS.format(self._entry_id),
                    outputs,
                    update_events["outputs"],
                )
                self._add_zones(outputs)
        if not {"database"}.isdisjoint(update_types):
            pipes, playlists = await asyncio.gather(
                self._api.get_pipes(), self._api.get_playlists()
            )
            update_events["database"] = asyncio.Event()
            async_dispatcher_send(
                self.hass,
                SIGNAL_UPDATE_DATABASE.format(self._entry_id),
                pipes,
                playlists,
                update_events["database"],
            )
        if not {"update", "config"}.isdisjoint(update_types):  # not supported
            _LOGGER.debug("update/config notifications neither requested nor supported")
        if not {"player", "options", "volume"}.isdisjoint(
            update_types
        ):  # update player
            player = await self._api.get_request("player")
            if player:
                update_events["player"] = asyncio.Event()
                if update_events.get("queue"):
                    await update_events[
                        "queue"
                    ].wait()  # make sure queue done before player for async_play_media
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_UPDATE_PLAYER.format(self._entry_id),
                    player,
                    update_events["player"],
                )
        if update_events:
            await asyncio.wait(
                [asyncio.create_task(event.wait()) for event in update_events.values()]
            )  # make sure callbacks done before update
            async_dispatcher_send(
                self.hass, SIGNAL_UPDATE_MASTER.format(self._entry_id), True
            )

    def _add_zones(self, outputs):
        outputs_to_add = []
        for output in outputs:
            if output["id"] not in self._all_output_ids:
                self._all_output_ids.add(output["id"])
                outputs_to_add.append(output)
        if outputs_to_add:
            async_dispatcher_send(
                self.hass,
                SIGNAL_ADD_ZONES.format(self._entry_id),
                self._api,
                outputs_to_add,
            )
