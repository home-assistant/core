"""MediaPlayer platform for Roon integration."""
import logging

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
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
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    DEVICE_DEFAULT_NAME,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.util import convert
from homeassistant.util.dt import utcnow

from .const import DOMAIN

SUPPORT_ROON = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_SET
    | SUPPORT_STOP
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_SEEK
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_VOLUME_STEP
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Roon MediaPlayer from Config Entry."""
    roon_server = hass.data[DOMAIN][config_entry.entry_id]
    media_players = set()

    @callback
    def async_update_media_player(player_data):
        """Add or update Roon MediaPlayer."""
        dev_id = player_data["dev_id"]
        if dev_id not in media_players:
            # new player!
            media_player = RoonDevice(roon_server, player_data)
            media_players.add(dev_id)
            async_add_entities([media_player])
        else:
            # update existing player
            async_dispatcher_send(
                hass, f"room_media_player_update_{dev_id}", player_data
            )

    # start listening for players to be added or changed by the server component
    async_dispatcher_connect(hass, "roon_media_player", async_update_media_player)


class RoonDevice(MediaPlayerEntity):
    """Representation of an Roon device."""

    def __init__(self, server, player_data):
        """Initialize Roon device object."""
        self._remove_signal_status = None
        self._server = server
        self._available = True
        self._last_position_update = None
        self._supports_standby = False
        self._state = STATE_IDLE
        self._last_playlist = None
        self._last_media = None
        self._unique_id = None
        self._zone_id = None
        self._output_id = None
        self._name = DEVICE_DEFAULT_NAME
        self._media_title = None
        self._media_album_name = None
        self._media_artist = None
        self._media_position = 0
        self._media_duration = 0
        self._is_volume_muted = False
        self._volume_step = 0
        self._shuffle = False
        self._media_image_url = None
        self._volume_level = 0
        self.update_data(player_data)

    async def async_added_to_hass(self):
        """Register callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"room_media_player_update_{self.unique_id}",
                self.async_update_callback,
            )
        )

    @callback
    def async_update_callback(self, player_data):
        """Handle device updates."""
        self.update_data(player_data)
        self.async_write_ha_state()

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_ROON

    @property
    def device_info(self):
        """Return the device info."""
        dev_model = "player"
        if self.player_data.get("source_controls"):
            dev_model = self.player_data["source_controls"][0].get("display_name")
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "RoonLabs",
            "model": dev_model,
            "via_hub": (DOMAIN, self._server.host),
        }

    def update_data(self, player_data=None):
        """Update session object."""
        if player_data:
            self.player_data = player_data
        if not self.player_data["is_available"]:
            # this player was removed
            self._available = False
            self._state = STATE_OFF
        else:
            self._available = True
            # determine player state
            self.update_state()
            if self.state == STATE_PLAYING:
                self._last_position_update = utcnow()

    def update_state(self):
        """Update the power state and player state."""
        new_state = ""
        # power state from source control (if supported)
        if "source_controls" in self.player_data:
            for source in self.player_data["source_controls"]:
                if source["supports_standby"] and source["status"] != "indeterminate":
                    self._supports_standby = True
                    if source["status"] in ["standby", "deselected"]:
                        new_state = STATE_OFF
                    break
        # determine player state
        if not new_state:
            if self.player_data["state"] == "playing":
                new_state = STATE_PLAYING
            elif self.player_data["state"] == "loading":
                new_state = STATE_PLAYING
            elif self.player_data["state"] == "stopped":
                new_state = STATE_IDLE
            elif self.player_data["state"] == "paused":
                new_state = STATE_PAUSED
            else:
                new_state = STATE_IDLE
        self._state = new_state
        self._unique_id = self.player_data["dev_id"]
        self._zone_id = self.player_data["zone_id"]
        self._output_id = self.player_data["output_id"]
        self._name = self.player_data["display_name"]
        self._is_volume_muted = self.player_data["volume"]["is_muted"]
        self._volume_step = convert(self.player_data["volume"]["step"], int, 0)
        self._shuffle = self.player_data["settings"]["shuffle"]

        if self.player_data["volume"]["type"] == "db":
            volume = (
                convert(self.player_data["volume"]["value"], float, 0.0) / 80 * 100
                + 100
            )
        else:
            volume = convert(self.player_data["volume"]["value"], float, 0.0)
        self._volume_level = convert(volume, int, 0) / 100

        try:
            self._media_title = self.player_data["now_playing"]["three_line"]["line1"]
            self._media_artist = self.player_data["now_playing"]["three_line"]["line2"]
            self._media_album_name = self.player_data["now_playing"]["three_line"][
                "line3"
            ]
            self._media_position = convert(
                self.player_data["now_playing"]["seek_position"], int, 0
            )
            self._media_duration = convert(
                self.player_data["now_playing"]["length"], int, 0
            )
            try:
                image_id = self.player_data["now_playing"]["image_key"]
                self._media_image_url = self._server.roonapi.get_image(image_id)
            except KeyError:
                self._media_image_url = None
        except KeyError:
            self._media_title = None
            self._media_album_name = None
            self._media_artist = None
            self._media_position = 0
            self._media_duration = 0
            self._media_image_url = None

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        # Returns value from homeassistant.util.dt.utcnow().
        return self._last_position_update

    @property
    def unique_id(self):
        """Return the id of this roon client."""
        return self._unique_id

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def zone_id(self):
        """Return current session Id."""
        return self._zone_id

    @property
    def output_id(self):
        """Return current session Id."""
        return self._output_id

    @property
    def name(self):
        """Return device name."""
        return self._name

    @property
    def media_title(self):
        """Return title currently playing."""
        return self._media_title

    @property
    def media_album_name(self):
        """Album name of current playing media (Music track only)."""
        return self._media_album_name

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        return self._media_artist

    @property
    def media_album_artist(self):
        """Album artist of current playing media (Music track only)."""
        return self._media_artist

    @property
    def media_playlist(self):
        """Title of Playlist currently playing."""
        return self._last_playlist

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._media_image_url

    @property
    def media_position(self):
        """Return position currently playing."""
        return self._media_position

    @property
    def media_duration(self):
        """Return total runtime length."""
        return self._media_duration

    @property
    def volume_level(self):
        """Return current volume level."""
        return self._volume_level

    @property
    def is_volume_muted(self):
        """Return mute state."""
        return self._is_volume_muted

    @property
    def volume_step(self):
        """.Return volume step size."""
        return self._volume_step

    @property
    def supports_standby(self):
        """Return power state of source controls."""
        return self._supports_standby

    @property
    def state(self):
        """Return current playstate of the device."""
        return self._state

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return self._shuffle

    def media_play(self):
        """Send play command to device."""
        self._server.roonapi.playback_control(self.output_id, "play")

    def media_pause(self):
        """Send pause command to device."""
        self._server.roonapi.playback_control(self.output_id, "pause")

    def media_play_pause(self):
        """Toggle play command to device."""
        self._server.roonapi.playback_control(self.output_id, "playpause")

    def media_stop(self):
        """Send stop command to device."""
        self._server.roonapi.playback_control(self.output_id, "stop")

    def media_next_track(self):
        """Send next track command to device."""
        self._server.roonapi.playback_control(self.output_id, "next")

    def media_previous_track(self):
        """Send previous track command to device."""
        self._server.roonapi.playback_control(self.output_id, "previous")

    def media_seek(self, position):
        """Send seek command to device."""
        self._server.roonapi.seek(self.output_id, position)
        # Seek doesn't cause an async update - so force one
        self._media_position = position
        self.schedule_update_ha_state()

    def set_volume_level(self, volume):
        """Send new volume_level to device."""
        volume = int(volume * 100)
        self._server.roonapi.change_volume(self.output_id, volume)

    def mute_volume(self, mute=True):
        """Send mute/unmute to device."""
        self._server.roonapi.mute(self.output_id, mute)

    def volume_up(self):
        """Send new volume_level to device."""
        self._server.roonapi.change_volume(self.output_id, 3, "relative")

    def volume_down(self):
        """Send new volume_level to device."""
        self._server.roonapi.change_volume(self.output_id, -3, "relative")

    def turn_on(self):
        """Turn on device (if supported)."""
        if not (self.supports_standby and "source_controls" in self.player_data):
            self.media_play()
            return
        for source in self.player_data["source_controls"]:
            if source["supports_standby"] and source["status"] != "indeterminate":
                self._server.roonapi.convenience_switch(
                    self.output_id, source["control_key"]
                )
                return

    def turn_off(self):
        """Turn off device (if supported)."""
        if not (self.supports_standby and "source_controls" in self.player_data):
            self.media_stop()
            return

        for source in self.player_data["source_controls"]:
            if source["supports_standby"] and not source["status"] == "indeterminate":
                self._server.roonapi.standby(self.output_id, source["control_key"])
                return

    def set_shuffle(self, shuffle):
        """Set shuffle state."""
        self._server.roonapi.shuffle(self.output_id, shuffle)

    def play_media(self, media_type, media_id, **kwargs):
        """Send the play_media command to the media player."""
        # Roon itself doesn't support playback of media by filename/url so this a bit of a workaround.
        media_type = media_type.lower()
        if media_type == "radio":
            if self._server.roonapi.play_radio(self.zone_id, media_id):
                self._last_playlist = media_id
                self._last_media = media_id
        elif media_type == "playlist":
            if self._server.roonapi.play_playlist(
                self.zone_id, media_id, shuffle=False
            ):
                self._last_playlist = media_id
        elif media_type == "shuffleplaylist":
            if self._server.roonapi.play_playlist(self.zone_id, media_id, shuffle=True):
                self._last_playlist = media_id
        elif media_type == "queueplaylist":
            self._server.roonapi.queue_playlist(self.zone_id, media_id)
        elif media_type == "genre":
            self._server.roonapi.play_genre(self.zone_id, media_id)
        else:
            _LOGGER.error(
                "Playback requested of unsupported type: %s --> %s",
                media_type,
                media_id,
            )
