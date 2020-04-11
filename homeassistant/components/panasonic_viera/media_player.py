"""Support for interface with a Panasonic Viera TV."""
from functools import partial
import logging
from urllib.request import URLError

from panasonic_viera import EncryptionRequired, Keys, RemoteControl

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
    ATTR_ENTITY_ID,
    CONF_BROADCAST_ADDRESS,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers.script import Script

from .const import (
    CONF_APP_ID,
    CONF_ENCRYPTION_KEY,
    CONF_ON_ACTION,
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
    port = config[CONF_PORT]
    name = config[CONF_NAME]

    on_action = config[CONF_ON_ACTION]
    if on_action:
        on_action = Script(hass, on_action)

    params = {}
    if CONF_APP_ID in config and CONF_ENCRYPTION_KEY in config:
        params["app_id"] = config[CONF_APP_ID]
        params["encryption_key"] = config[CONF_ENCRYPTION_KEY]

    remote = await hass.async_add_executor_job(
        partial(Remote, hass, host, port, **params)
    )
    await remote.async_create_remote_control(during_setup=True)

    tv = PanasonicVieraTVDevice(hass, remote, name, on_action,)

    async_add_entities([tv])

    return True


class PanasonicVieraTVDevice(MediaPlayerDevice):
    """Representation of a Panasonic Viera TV."""

    def __init__(
        self, hass, remote, name, on_action, uuid=None,
    ):
        """Initialize the Panasonic device."""
        # Save a reference to the imported class
        self._hass = hass

        self._remote = remote

        self._name = name
        self._on_action = on_action

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
        return self._remote._state

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._remote._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._remote._muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._on_action:
            return SUPPORT_VIERATV | SUPPORT_TURN_ON
        return SUPPORT_VIERATV

    async def async_update(self):
        """Retrieve the latest data."""
        await self._remote.async_update()

    async def async_turn_on(self):
        """Turn on the media player."""
        if self._on_action:
            await self._on_action.async_run()

    async def async_turn_off(self):
        """Turn off media player."""
        if self._remote._state != STATE_OFF:
            await self._remote.async_send_key(Keys.power)
            self._remote._state = STATE_OFF

    async def async_volume_up(self):
        """Volume up the media player."""
        await self._remote.async_send_key(Keys.volume_up)

    async def async_volume_down(self):
        """Volume down media player."""
        await self._remote.async_send_key(Keys.volume_down)

    async def async_mute_volume(self, mute):
        """Send mute command."""
        await self._remote.async_set_mute(mute)

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        await self._remote.async_set_volume(volume)

    async def async_media_play_pause(self):
        """Simulate play pause media player."""
        if self._remote._playing:
            await self._remote.async_send_key(Keys.pause)
            self._remote._playing = False
        else:
            await self._remote.async_send_key(Keys.play)
            self._remote._playing = True

    async def async_media_play(self):
        """Send play command."""
        await self._remote.async_send_key(Keys.play)
        self._remote._playing = True

    async def async_media_pause(self):
        """Send pause command."""
        await self._remote.async_send_key(Keys.pause)
        self._remote._playing = True

    async def async_media_stop(self):
        """Stop playback."""
        await self._remote.async_send_key(Keys.stop)

    async def async_media_next_track(self):
        """Send the fast forward command."""
        await self._remote.async_send_key(Keys.fast_forward)

    async def async_media_previous_track(self):
        """Send the rewind command."""
        await self._remote.async_send_key(Keys.rewind)

    async def async_play_media(self, media_type, media_id):
        """Play media."""
        await self._remote.async_play_media(media_type, media_id)


class Remote:
    def __init__(
        self, hass, host, port, app_id=None, encryption_key=None,
    ):
        self._hass = hass
        self._host = host
        self._port = port
        self._app_id = app_id
        self._encryption_key = encryption_key

        self._state = None
        self._volume = 0
        self._muted = False
        self._playing = True

        self._control = None

    async def async_create_remote_control(self, during_setup=False):
        control_existed = self._control is not None
        try:
            params = {}
            if self._app_id and self._encryption_key:
                params["app_id"] = self._app_id
                params["encryption_key"] = self._encryption_key

            self._control = await self._hass.async_add_executor_job(
                partial(RemoteControl, self._host, self._port, **params)
            )

            self._state = STATE_ON
        except (TimeoutError, URLError, OSError) as err:
            if control_existed or during_setup:
                _LOGGER.error("Could not establish remote connection: %s", err)
                self._remote = None
                self._state = STATE_OFF
        except Exception as err:
            if control_existed or during_setup:
                _LOGGER.error("An unknown error occured: %s", err)
                self._remote = None
                self._state = STATE_OFF

    async def async_update(self):
        """Retrieve the latest data."""
        try:
            if self._control is None:
                raise Exception

            self._muted = self._control.get_mute()
            self._volume = self._control.get_volume() / 100
            self._state = STATE_ON
        except EncryptionRequired:
            _LOGGER.error("The connection couldn't be encrypted.")
        except Exception:
            self._state = STATE_OFF
            await self.async_create_remote_control()

    async def async_send_key(self, key):
        """Send a key to the TV and handles exceptions."""
        if self._control:
            try:
                self._control.send_key(key)
            except EncryptionRequired:
                _LOGGER.error("The connection couldn't be encrypted.")
            except Exception:
                self._state = STATE_OFF
                await self.async_create_remote_control()

    async def async_set_mute(self, enable):
        if self._control:
            try:
                self._control.set_mute(enable)
            except EncryptionRequired:
                _LOGGER.error("The connection couldn't be encrypted.")
            except Exception:
                self._state = STATE_OFF
                await self.async_create_remote_control()

    async def async_set_volume(self, volume):
        """Set volume level, range 0..1."""
        if self._control:
            volume = int(volume * 100)
            try:
                self._control.set_volume(volume)
            except EncryptionRequired:
                _LOGGER.error("The connection couldn't be encrypted.")
            except Exception:
                self._state = STATE_OFF
                await self.async_create_remote_control()

    async def async_play_media(self, media_type, media_id):
        """Play media."""
        if not self._control:
            return

        _LOGGER.debug("Play media: %s (%s)", media_id, media_type)

        if media_type == MEDIA_TYPE_URL:
            try:
                self._control.open_webpage(media_id)
            except EncryptionRequired:
                _LOGGER.error("The connection couldn't be encrypted.")
            except Exception:
                self._state = STATE_OFF
                await self.async_create_remote_control()
        else:
            _LOGGER.warning("Unsupported media_type: %s", media_type)
