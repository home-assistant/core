"""
Support to interact with a ExoPlayer on Android via HTTP and MQTT.

"""
import asyncio
import json
import logging
from typing import Optional

from aisapi.ws import AisWebService

import homeassistant.components.ais_dom.ais_global as ais_global
from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.const import (
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_NAME,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.helpers import aiohttp_client
import homeassistant.util.dt as dt_util

from .media_browser import browse_media

_LOGGER = logging.getLogger(__name__)

SUPPORT_EXO = (
    SUPPORT_PAUSE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PLAY
    | SUPPORT_STOP
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_SEEK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_SELECT_SOUND_MODE
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_BROWSE_MEDIA
)


def _publish_command_to_frame(hass, device_ip, key, val):
    if device_ip == "localhost":
        hass.services.call(
            "ais_ai_service",
            "publish_command_to_frame",
            {"key": key, "val": val, "ip": "localhost"},
        )

    else:
        hass.services.call(
            "ais_ai_service",
            "publish_command_to_frame",
            {"key": key, "val": val, "ip": device_ip},
        )


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the ExoPlayer platform."""

    async def async_redirect_media(service):
        if "entity_id" not in service.data:
            return

        entity_id = service.data["entity_id"]
        state = hass.states.get(ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID)
        attr = state.attributes
        media_content_id = attr.get("media_content_id")
        if media_content_id is None:
            return
        # 0. push media info to ais to share with client
        j_media_info = {
            "media_title": device.media_title,
            "media_source": device.source,
            "media_stream_image": device.media_stream_image,
            "media_album_name": device.media_album_name,
            "media_content_id": device.media_content_id,
        }
        await ais_gate.share_media_full_info(j_media_info)

        # 1. pause internal player
        await hass.services.async_call(
            "media_player",
            "media_pause",
            {"entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID},
        )
        # 2. redirect media to player
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": entity_id,
                "media_content_type": "music",
                "media_content_id": media_content_id,
            },
        )

    def play_text_or_url(service):
        # text
        text = service.data["text"].strip()
        if text.lower().startswith(("http:", "https:", "rtsp:", "mms:")):
            hass.services.call(
                "media_player",
                "play_media",
                {
                    "entity_id": "media_player.wbudowany_glosnik",
                    "media_content_type": "music",
                    "media_content_id": text,
                },
            )
        else:
            # nothing special here - just say (grouping is done in say_it service)
            hass.services.call("ais_ai_service", "say_it", {"text": text})

    hass.services.async_register(
        "ais_exo_player", "redirect_media", async_redirect_media
    )
    hass.services.async_register("ais_exo_player", "play_text_or_url", play_text_or_url)

    name = config.get(CONF_NAME)
    _ip = config.get(CONF_IP_ADDRESS)
    _unique_id = config.get("unique_id")

    web_session = aiohttp_client.async_get_clientsession(hass)
    ais_gate = AisWebService(hass.loop, web_session, _ip)

    device = ExoPlayerDevice(_ip, _unique_id, name, ais_gate)
    _LOGGER.info("device: " + str(device))
    async_add_devices([device], True)


class ExoPlayerDevice(MediaPlayerEntity):
    """Representation of a ExoPlayer ."""

    # pylint: disable=no-member
    def __init__(self, device_ip, unique_id, name, ais_gate_instance):
        """Initialize the ExoPlayer device."""

        self._ais_gate = ais_gate_instance
        self._device_ip = device_ip
        self._unique_id = unique_id
        self._name = name
        self._status = None
        self._playing = False
        self._qos = 2
        self._stream_image = None
        self._media_title = None
        self._media_source = None
        self._album_name = None
        self._sound_mode = "NORMAL"
        self._playlists = [
            ais_global.G_AN_RADIO,
            ais_global.G_AN_PODCAST,
            ais_global.G_AN_MUSIC,
            ais_global.G_AN_AUDIOBOOK,
            ais_global.G_AN_NEWS,
            ais_global.G_AN_LOCAL,
            ais_global.G_AN_SPOTIFY,
            ais_global.G_AN_FAVORITE,
        ]
        self._currentplaylist = None
        self._media_status_received_time = None
        self._media_position = 0
        self._duration = 0
        self._media_content_id = None
        self._volume_level = 0.5
        self._shuffle = False
        self._assistant_audio = False

        if device_ip == "localhost":
            self._is_master = True
        else:
            self._is_master = False

    def set_repeat(self, repeat):
        pass

    def turn_on(self):
        pass

    def turn_off(self):
        pass

    def set_volume_level(self, volume):
        self._volume_level = volume
        vol = int(volume * 100)
        _publish_command_to_frame(self.hass, self._device_ip, "setVolume", vol)

    def select_sound_mode(self, sound_mode):
        self._sound_mode = sound_mode
        self.hass.services.call(
            "ais_amplifier_service", "change_sound_mode", {"mode": sound_mode}
        )

    def clear_playlist(self):
        pass

    @asyncio.coroutine
    def async_added_to_hass(self):
        pass

    def _fetch_status(self):
        """Fetch status from ExoPlayer."""
        # INFO - we are not fetching the status from player
        # exp player and spotify is pushing the status to asystent domowy

    @property
    def source(self):
        """Name of the current input source."""
        return self._currentplaylist

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return self._playlists

    def select_source(self, source):
        """Choose a different available playlist and play it."""
        # TODO
        pass

    @property
    def volume_level(self):
        """Return the volume level of the Player"""
        return self._volume_level

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        return float(self._duration) // 1000

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return self._shuffle

    def set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        self._shuffle = shuffle
        _publish_command_to_frame(
            self.hass, self._device_ip, "setPlayerShuffle", self._shuffle
        )

    def media_seek(self, position):
        """Seek the media to a specific location."""
        if position == 0:
            _publish_command_to_frame(self.hass, self._device_ip, "seekTo", -5000)
        elif position == 1:
            _publish_command_to_frame(self.hass, self._device_ip, "seekTo", 5000)
        else:
            _publish_command_to_frame(
                self.hass, self._device_ip, "skipTo", position * 1000
            )
            self._media_status_received_time = dt_util.utcnow()
            self._media_position = position * 1000

    def volume_up(self):
        """Service to send the exo the command for volume up."""
        self._volume_level = min(self._volume_level + 0.0667, 1)
        _publish_command_to_frame(self.hass, self._device_ip, "upVolume", True)

    def volume_down(self):
        """Service to send the exo the command for volume down."""
        self._volume_level = max(self._volume_level - 0.0667, 0)
        _publish_command_to_frame(self.hass, self._device_ip, "downVolume", True)

    def mute_volume(self, mute):
        """Service to send the exo the command for mute."""
        pass
        # TODO

    @property
    def sound_mode(self):
        """Return the current matched sound mode."""
        return self._sound_mode

    @property
    def sound_mode_list(self):
        """Return a list of available sound modes."""
        return [
            "NORMAL",
            "BOOST",
            "TREBLE",
            "POP",
            "ROCK",
            "CLASSIC",
            "JAZZ",
            "DANCE",
            "R&P",
        ]

    @property
    def available(self):
        """True if ExoPlayer is available and connected."""
        return True

    def update(self):
        """Get the latest data and update the state."""
        self._fetch_status()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def media_image_url(self):
        """Return the image url of current playing media."""
        if self._stream_image is None:
            return "http://localhost:8180/static/icons/tile-win-310x150.png"
        return self._stream_image

    @property
    def state(self):
        """Return the media state."""

        if self._playing is False:
            return STATE_PAUSED
        else:
            if self._status == 1:
                return STATE_IDLE
            if self._status == 2:
                return STATE_PAUSED
            if self._status == 3:
                return STATE_PLAYING
            if self._status == 4:
                return STATE_PAUSED

        return STATE_OFF

    @property
    def media_title(self):
        """Return the title of current playing media."""
        return self._media_title

    @property
    def media_album_name(self):
        """Album of current playing media"""
        return self._album_name

    @property
    def app_name(self):
        """Name of the current running app."""
        app = None
        if self._media_source is not None:
            app = self._media_source
            if self._album_name is not None:
                app = str(app) + " " + str(self._album_name)
        return app

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_EXO

    @property
    def media_content_id(self):
        """The media content id"""
        return self._media_content_id

    @property
    def media_stream_image(self):
        """The media content id"""
        return self._stream_image

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        position = float(self._media_position) // 1000
        # if self._status == 3 and self._media_status_received_time is not None:
        #     position += (dt_util.utcnow() - self._media_status_received_time).total_seconds()
        return int(position)

    @property
    def device_state_attributes(self):
        """Return the specific state attributes of the player."""
        attr = {
            "device_ip": self._device_ip,
            "unique_id": self._unique_id,
            "media_stream_image": self._stream_image,
            "friendly_name": "Podłączony głośnik",
        }
        return attr

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._unique_id

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid.
        Returns value from homeassistant.util.dt.utcnow().
        """
        return self._media_status_received_time

    def media_play(self):
        """Service to send the ExoPlayer the command for play/pause."""
        _publish_command_to_frame(self.hass, self._device_ip, "pauseAudio", False)
        self._playing = True
        self._status = 3

    def media_pause(self):
        """Service to send the ExoPlayer the command for play/pause."""
        # to have more accurate media_position
        self._fetch_status()
        _publish_command_to_frame(self.hass, self._device_ip, "pauseAudio", True)
        self._playing = False

    def media_stop(self):
        """Service to send the ExoPlayer the command for stop."""
        _publish_command_to_frame(self.hass, self._device_ip, "pauseAudio", True)
        self._playing = False

    def media_next_track(self):
        """Service to send the ExoPlayer the command for next track."""
        if self._media_source == ais_global.G_AN_LOCAL:
            self.hass.services.call("ais_drives_service", "play_next")
        else:
            self.hass.services.call(
                "ais_cloud", "play_next", {"media_source": self._media_source}
            )

    def media_previous_track(self):
        """Service to send the ExoPlayer the command for previous track."""
        if self._media_source == ais_global.G_AN_LOCAL:
            self.hass.services.call("ais_drives_service", "play_prev")
        else:
            self.hass.services.call(
                "ais_cloud", "play_prev", {"media_source": self._media_source}
            )

    def play_media(self, media_type, media_content_id, **kwargs):
        """Send the media player the command for playing a media."""
        if media_type == "ais_content_info":
            j_info = json.loads(media_content_id)
            # set image and name and id on list to be able to set correct bookmark and favorites
            ais_global.G_CURR_MEDIA_CONTENT = j_info
            # play
            self._media_content_id = j_info["media_content_id"]
            self._media_status_received_time = dt_util.utcnow()
            if "media_position_ms" in j_info:
                self._media_position = j_info["media_position_ms"]
            else:
                self._media_position = 0
            if "IMAGE_URL" not in j_info:
                self._stream_image = "/static/icons/tile-win-310x150.png"
            else:
                self._stream_image = j_info["IMAGE_URL"]
            self._media_title = j_info["NAME"]
            if j_info["MEDIA_SOURCE"] == ais_global.G_AN_GOOGLE_ASSISTANT:
                # do no change self._media_source
                self._assistant_audio = True
            else:
                self._assistant_audio = False
                self._media_source = j_info["MEDIA_SOURCE"]
            self._currentplaylist = j_info["MEDIA_SOURCE"]
            if "ALBUM_NAME" in j_info:
                self._album_name = j_info["ALBUM_NAME"]
            else:
                self._album_name = ""
            if "DURATION" in j_info:
                self._duration = j_info["DURATION"]

            j_media_info = {
                "media_title": self._media_title,
                "media_source": self._media_source,
                "media_stream_image": self._stream_image,
                "media_album_name": self._album_name,
                "media_content_id": self._media_content_id,
                "setPlayerShuffle": self._shuffle,
                "setMediaPosition": self._media_position,
            }

            _publish_command_to_frame(
                self.hass, self._device_ip, "playAudioFullInfo", j_media_info
            )

            self._playing = True
            self._status = 3

            # go to media player context on localhost
            if self._device_ip == "localhost":
                # refresh state
                old_state = self.hass.states.get("media_player.wbudowany_glosnik")
                self.hass.states.set(
                    "media_player.wbudowany_glosnik",
                    STATE_PLAYING,
                    old_state.attributes,
                    force_update=True,
                )
                self.hass.services.call(
                    "ais_ai_service",
                    "process_command_from_frame",
                    {"topic": "ais/go_to_player", "payload": ""},
                )

        elif media_type == "ais_info":
            # TODO remove this - it is only used in one case - for local media_extractor
            # set only the audio info
            j_info = json.loads(media_content_id)
            ais_global.G_CURR_MEDIA_CONTENT = j_info
            if "IMAGE_URL" not in j_info:
                self._stream_image = "/static/icons/tile-win-310x150.png"
            else:
                self._stream_image = j_info["IMAGE_URL"]
            self._media_title = j_info["NAME"]
            self._media_source = j_info["MEDIA_SOURCE"]
            self._currentplaylist = j_info["MEDIA_SOURCE"]
            if "ALBUM_NAME" in j_info:
                self._album_name = j_info["ALBUM_NAME"]
            else:
                self._album_name = None
            if "DURATION" in j_info:
                self._duration = j_info["DURATION"]

            try:
                j_media_info = {
                    "media_title": self._media_title,
                    "media_source": self._media_source,
                    "media_stream_image": self._stream_image,
                    "media_album_name": self._album_name,
                }
                _publish_command_to_frame(
                    self.hass, self._device_ip, "setAudioInfo", j_media_info
                )
            except Exception as e:
                _LOGGER.debug("problem to publish setAudioInfo: " + str(e))

            self._playing = True
            self._status = 3
            # go to media player context on localhost
            if self._device_ip == "localhost":
                # refresh state
                old_state = self.hass.states.get("media_player.wbudowany_glosnik")
                self.hass.states.set(
                    "media_player.wbudowany_glosnik",
                    STATE_PLAYING,
                    old_state.attributes,
                    force_update=True,
                )
                self.hass.services.call(
                    "ais_ai_service",
                    "process_command_from_frame",
                    {"topic": "ais/go_to_player", "payload": ""},
                )

        elif media_type == "exo_info":
            self._media_status_received_time = dt_util.utcnow()
            try:
                message = json.loads(media_content_id.decode("utf8").replace("'", '"'))
            except Exception as e:
                message = json.loads(media_content_id)
            try:
                self._volume_level = message.get("currentVolume", 0) / 100
            except Exception as e:
                _LOGGER.warning("no currentVolume info: " + str(e))
            self._status = message.get("currentStatus", 0)
            self._playing = message.get("playing", False)
            self._media_position = message.get("currentPosition", 0)
            if "duration" in message:
                self._duration = message.get("duration", 0)
            temp_stream_image = message.get("media_stream_image", None)
            if temp_stream_image is not None:
                if temp_stream_image.startswith("spotify:image:"):
                    temp_stream_image = temp_stream_image.replace("spotify:image:", "")
                    self._stream_image = "https://i.scdn.co/image/" + temp_stream_image
                else:
                    self._stream_image = temp_stream_image
            self._media_title = message.get("currentMedia", "AI-Speaker")
            self._media_source = message.get("media_source", self._media_source)
            self._album_name = message.get("media_album_name", "AI-Speaker")

            # spotify info
            if self._media_source == ais_global.G_AN_SPOTIFY:
                # shuffle
                self._shuffle = message.get("isShuffling", False)
                # mark track on Spotify list
                state = self.hass.states.get("sensor.spotifylist")
                attr = state.attributes
                for i in range(len(attr)):
                    track = attr.get(i)
                    if track["uri"] == message.get("media_content_id", ""):
                        self.hass.states.async_set("sensor.spotifylist", i, attr)
                        break

            if "giveMeNextOne" in message:
                play_next = message.get("giveMeNextOne", False)
                # play next audio only if the current was not from assistant
                if play_next is True and self._assistant_audio is False:
                    # TODO remove bookmark
                    self.hass.async_add_job(
                        self.hass.services.async_call(
                            "media_player",
                            "media_next_track",
                            {"entity_id": "media_player.wbudowany_glosnik"},
                        )
                    )
        else:
            # do not call async from threads - this will it can lead to a deadlock!!!
            # if media_content_id.startswith("ais_"):
            #     from homeassistant.components.ais_exo_player import media_browser
            #
            #     media_content_id = media_browser.get_media_content_id_form_ais(
            #         self.hass, media_content_id
            #     )
            # this is currently used when the media are taken from gallery
            if media_content_id.startswith("ais_"):
                import requests

                if media_content_id.startswith("ais_tunein"):
                    url_to_call = media_content_id.split("/", 3)[3]
                    try:
                        response_text = requests.get(url_to_call, timeout=2).text
                        response_text = response_text.split("\n")[0]
                        if response_text.endswith(".pls"):
                            response_text = requests.get(response_text, timeout=2).text
                            media_content_id = response_text.split("\n")[1].replace(
                                "File1=", ""
                            )
                        if response_text.startswith("mms:"):
                            response_text = requests.get(
                                response_text.replace("mms:", "http:"), timeout=2
                            ).text
                            media_content_id = response_text.split("\n")[1].replace(
                                "Ref1=", ""
                            )
                    except Exception as e:
                        pass
                elif media_content_id.startswith("ais_spotify"):
                    media_content_id = media_content_id.replace("ais_spotify/", "")
            self._media_content_id = media_content_id
            self._media_position = 0
            self._media_status_received_time = dt_util.utcnow()
            _publish_command_to_frame(
                self.hass, self._device_ip, "playAudio", media_content_id
            )

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""
        result = await browse_media(self.hass, media_content_type, media_content_id)
        return result
