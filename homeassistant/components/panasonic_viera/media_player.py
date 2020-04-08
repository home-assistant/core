"""Support for interface with a Panasonic Viera TV."""
from functools import partial
import logging
from urllib.request import URLError

from panasonic_viera import RemoteControl
import wakeonlan

from homeassistant.components.media_player import MediaPlayerDevice
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_URL,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    STATE_OFF,
    STATE_ON,
)

from .const import (
    CONF_APP_ID,
    CONF_APP_POWER,
    CONF_ENCRYPTION_KEY,
    DEVICE_MANUFACTURER,
    DOMAIN,
)

SUPPORT_VIERATV = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_STOP
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Panasonic Viera TV from a config entry."""

    config = config_entry.data

    host = config[CONF_HOST]
    mac = config[CONF_MAC]
    broadcast = config[CONF_BROADCAST_ADDRESS]
    name = config[CONF_NAME]
    port = config[CONF_PORT]
    app_power = config[CONF_APP_POWER]

    uuid = mac if mac else host

    app_id = None
    encryption_key = None

    remote = None

    try:
        if CONF_APP_ID in config and CONF_ENCRYPTION_KEY in config:
            app_id = config[CONF_APP_ID]
            encryption_key = config[CONF_ENCRYPTION_KEY]
            remote = RemoteControl(
                host, port, app_id=app_id, encryption_key=encryption_key
            )
        else:
            remote = RemoteControl(host, port)
    except Exception as err:
        _LOGGER.error("Could not establish remote connection: " + repr(err))

    tv = PanasonicVieraTVDevice(
        hass,
        mac,
        name,
        remote,
        host,
        port,
        app_id,
        encryption_key,
        broadcast,
        app_power,
        uuid,
    )

    async_add_entities([tv])


class PanasonicVieraTVDevice(MediaPlayerDevice):
    """Representation of a Panasonic Viera TV."""

    def __init__(
        self,
        hass,
        mac,
        name,
        remote,
        host,
        port,
        app_id,
        encryption_key,
        broadcast,
        app_power,
        uuid=None,
    ):
        """Initialize the Panasonic device."""
        # Save a reference to the imported class
        self._remote = remote
        self._name = name
        self._muted = False
        self._playing = True
        self._state = None
        self._remote = remote
        self._host = host
        self._port = port
        self._app_id = app_id
        self._encryption_key = encryption_key
        self._broadcast = broadcast
        self._volume = 0
        self._app_power = app_power
        self._uuid = uuid

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this Viera TV."""
        return self._uuid

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._remote.state

    @property
    def available(self):
        """Return if True the device is available."""
        return self._remote.available

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._remote.volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._remote.muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_VIERATV

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": DEVICE_MANUFACTURER,
        }

    def update(self):
        """Retrieve the latest data and renew connection."""
        if self._remote:
            try:
                self._muted = self._remote.get_mute()
                self._volume = self._remote.get_volume() / 100
                self._state = STATE_ON
            except OSError:
                self._state = STATE_OFF

        old_remote = self._remote
        try:
            if self._app_id and self._encryption_key:
                self._remote = RemoteControl(
                    self._host,
                    self._port,
                    app_id=self._app_id,
                    encryption_key=self._encryption_key,
                )
            else:
                self._remote = RemoteControl(self._host, self._port)
        except Exception as err:
            if old_remote:
                _LOGGER.error("Could not establish remote connection: " + repr(err))

    def send_key(self, key):
        """Send a key to the tv and handles exceptions."""
        if self._remote:
            try:
                self._remote.send_key(key)
                self._state = STATE_ON
            except OSError:
                self._state = STATE_OFF
                return False
            return True

    def turn_on(self):
        """Turn on the media player."""
        if self._mac:
            self._wol.send_magic_packet(self._mac, ip_address=self._broadcast)
            self._state = STATE_ON
        elif self._app_power:
            if self._remote:
                self._remote.turn_on()
                self._state = STATE_ON

    def turn_off(self):
        """Turn off media player."""
        if self._remote and self._state != STATE_OFF:
            self._remote.turn_off()
            self._state = STATE_OFF

    async def async_volume_up(self):
        """Volume up the media player."""
        if self._remote:
            self._remote.volume_up()

    async def async_volume_down(self):
        """Volume down media player."""
        if self._remote:
            self._remote.volume_down()

    async def async_mute_volume(self, mute):
        """Send mute command."""
        if self._remote:
            self._remote.set_mute(mute)

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        if self._remote:
            volume = int(volume * 100)
            try:
                self._remote.set_volume(volume)
                self._state = STATE_ON
            except OSError:
                self._state = STATE_OFF

    async def async_media_play_pause(self):
        """Simulate play pause media player."""
        if self._remote:
            if self._playing:
                self.media_pause()
            else:
                self.media_play()

    async def async_media_play(self):
        """Send play command."""
        if self._remote:
            self._playing = True
            self._remote.media_play()

    def media_pause(self):
        """Send media pause command to media player."""
        if self._remote:
            self._playing = False
            self._remote.media_pause()

    def media_next_track(self):
        """Send next track command."""
        if self._remote:
            self._remote.media_next_track()

    def media_previous_track(self):
        """Send the previous track command."""
        if self._remote:
            self._remote.media_previous_track()

    async def async_play_media(self, media_type, media_id):
        """Play media."""
        if self._remote:
            _LOGGER.debug("Play media: %s (%s)", media_id, media_type)

            if media_type == MEDIA_TYPE_URL:
                try:
                    self._remote.open_webpage(media_id)
                except (TimeoutError, OSError):
                    self._state = STATE_OFF
            else:
                _LOGGER.warning("Unsupported media_type: %s", media_type)

    def media_stop(self):
        """Stop playback."""
        if self._remote:
            self.send_key("NRC_STOP-ONOFF")
