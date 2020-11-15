"""Media player support for Panasonic Viera TV."""
import logging

from panasonic_viera import Keys

from homeassistant.components.media_player import DEVICE_CLASS_TV, MediaPlayerEntity
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
from homeassistant.const import CONF_NAME

from .const import (
    ATTR_DEVICE_INFO,
    ATTR_MANUFACTURER,
    ATTR_MODEL_NUMBER,
    ATTR_REMOTE,
    ATTR_UDN,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL_NUMBER,
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

    remote = hass.data[DOMAIN][config_entry.entry_id][ATTR_REMOTE]
    name = config[CONF_NAME]
    device_info = config[ATTR_DEVICE_INFO]

    tv_device = PanasonicVieraTVEntity(remote, name, device_info)
    async_add_entities([tv_device])


class PanasonicVieraTVEntity(MediaPlayerEntity):
    """Representation of a Panasonic Viera TV."""

    def __init__(self, remote, name, device_info):
        """Initialize the entity."""
        self._remote = remote
        self._name = name
        self._device_info = device_info

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        if self._device_info is None:
            return None
        return self._device_info[ATTR_UDN]

    @property
    def device_info(self):
        """Return device specific attributes."""
        if self._device_info is None:
            return None
        return {
            "name": self._name,
            "identifiers": {(DOMAIN, self._device_info[ATTR_UDN])},
            "manufacturer": self._device_info.get(
                ATTR_MANUFACTURER, DEFAULT_MANUFACTURER
            ),
            "model": self._device_info.get(ATTR_MODEL_NUMBER, DEFAULT_MODEL_NUMBER),
        }

    @property
    def device_class(self):
        """Return the device class of the device."""
        return DEVICE_CLASS_TV

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
        """Return True if the device is available."""
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
        await self._remote.async_turn_on(context=self._context)

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
        if media_type != MEDIA_TYPE_URL:
            _LOGGER.warning("Unsupported media_type: %s", media_type)
            return

        await self._remote.async_play_media(media_type, media_id)
