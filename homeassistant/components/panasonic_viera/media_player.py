"""Support for interface with a Panasonic Viera TV."""
from functools import partial
import logging
from urllib.request import URLError

from panasonic_viera import EncryptionRequired, Keys, RemoteControl, SOAPError

from homeassistant.components.media_player import MediaPlayerEntity
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
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, STATE_OFF, STATE_ON
from homeassistant.helpers.script import Script

from .const import CONF_APP_ID, CONF_ENCRYPTION_KEY, CONF_ON_ACTION

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
    if on_action is not None:
        on_action = Script(hass, on_action)

    params = {}
    if CONF_APP_ID in config and CONF_ENCRYPTION_KEY in config:
        params["app_id"] = config[CONF_APP_ID]
        params["encryption_key"] = config[CONF_ENCRYPTION_KEY]

    remote = Remote(hass, host, port, on_action, **params)
    await remote.async_create_remote_control(during_setup=True)

    tv_device = PanasonicVieraTVDevice(remote, name)

    async_add_entities([tv_device])


class PanasonicVieraTVDevice(MediaPlayerEntity):
    """Representation of a Panasonic Viera TV."""

    def __init__(
        self, remote, name, uuid=None,
    ):
        """Initialize the Panasonic device."""
        # Save a reference to the imported class
        self._remote = remote
        self._name = name
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

    async def async_update(self):
        """Retrieve the latest data."""
        await self._remote.async_update()

    async def async_turn_on(self):
        """Turn on the media player."""
        await self._remote.async_turn_on()

    async def async_turn_off(self):
        """Turn off media player."""
        await self._remote.async_turn_off()

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
        if self._remote.playing:
            await self._remote.async_send_key(Keys.pause)
            self._remote.playing = False
        else:
            await self._remote.async_send_key(Keys.play)
            self._remote.playing = True

    async def async_media_play(self):
        """Send play command."""
        await self._remote.async_send_key(Keys.play)
        self._remote.playing = True

    async def async_media_pause(self):
        """Send pause command."""
        await self._remote.async_send_key(Keys.pause)
        self._remote.playing = False

    async def async_media_stop(self):
        """Stop playback."""
        await self._remote.async_send_key(Keys.stop)

    async def async_media_next_track(self):
        """Send the fast forward command."""
        await self._remote.async_send_key(Keys.fast_forward)

    async def async_media_previous_track(self):
        """Send the rewind command."""
        await self._remote.async_send_key(Keys.rewind)

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play media."""
        await self._remote.async_play_media(media_type, media_id)


class Remote:
    """The Remote class. It stores the TV properties and the remote control connection itself."""

    def __init__(
        self, hass, host, port, on_action=None, app_id=None, encryption_key=None,
    ):
        """Initialize the Remote class."""
        self._hass = hass

        self._host = host
        self._port = port

        self._on_action = on_action

        self._app_id = app_id
        self._encryption_key = encryption_key

        self.state = None
        self.available = False
        self.volume = 0
        self.muted = False
        self.playing = True

        self._control = None

    async def async_create_remote_control(self, during_setup=False):
        """Create remote control."""
        control_existed = self._control is not None
        try:
            params = {}
            if self._app_id and self._encryption_key:
                params["app_id"] = self._app_id
                params["encryption_key"] = self._encryption_key

            self._control = await self._hass.async_add_executor_job(
                partial(RemoteControl, self._host, self._port, **params)
            )

            self.state = STATE_ON
            self.available = True
        except (TimeoutError, URLError, SOAPError, OSError) as err:
            if control_existed or during_setup:
                _LOGGER.error("Could not establish remote connection: %s", err)

            self._control = None
            self.state = STATE_OFF
            self.available = self._on_action is not None
        except Exception as err:  # pylint: disable=broad-except
            if control_existed or during_setup:
                _LOGGER.exception("An unknown error occurred: %s", err)
                self._control = None
                self.state = STATE_OFF
                self.available = self._on_action is not None

    async def async_update(self):
        """Update device data."""
        if self._control is None:
            await self.async_create_remote_control()
            return

        await self._handle_errors(self._update)

    async def _update(self):
        """Retrieve the latest data."""
        self.muted = self._control.get_mute()
        self.volume = self._control.get_volume() / 100

        self.state = STATE_ON
        self.available = True

    async def async_send_key(self, key):
        """Send a key to the TV and handle exceptions."""
        await self._handle_errors(self._control.send_key, key)

    async def async_turn_on(self):
        """Turn on the TV."""
        if self._on_action is not None:
            await self._on_action.async_run()
            self.state = STATE_ON
        elif self.state != STATE_ON:
            await self.async_send_key(Keys.power)
            self.state = STATE_ON

    async def async_turn_off(self):
        """Turn off the TV."""
        if self.state != STATE_OFF:
            await self.async_send_key(Keys.power)
            self.state = STATE_OFF
            await self.async_update()

    async def async_set_mute(self, enable):
        """Set mute based on 'enable'."""
        await self._handle_errors(self._control.set_mute, enable)

    async def async_set_volume(self, volume):
        """Set volume level, range 0..1."""
        volume = int(volume * 100)
        await self._handle_errors(self._control.set_volume, volume)

    async def async_play_media(self, media_type, media_id):
        """Play media."""
        _LOGGER.debug("Play media: %s (%s)", media_id, media_type)

        if media_type != MEDIA_TYPE_URL:
            _LOGGER.warning("Unsupported media_type: %s", media_type)
            return

        await self._handle_errors(self._control.open_webpage, media_id)

    async def _handle_errors(self, func, *args):
        """Handle errors from func, set available and reconnect if needed."""
        try:
            await self._hass.async_add_executor_job(func, *args)
        except EncryptionRequired:
            _LOGGER.error("The connection couldn't be encrypted")
        except (TimeoutError, URLError, SOAPError, OSError):
            self.state = STATE_OFF
            self.available = self._on_action is not None
            await self.async_create_remote_control()
