"""Media player support for Panasonic Viera TV."""
from __future__ import annotations

import logging

from panasonic_viera import Keys

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player.browse_media import (
    async_process_play_media_url,
)
from homeassistant.components.media_player.const import MEDIA_TYPE_URL
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Panasonic Viera TV from a config entry."""

    config = config_entry.data

    remote = hass.data[DOMAIN][config_entry.entry_id][ATTR_REMOTE]
    name = config[CONF_NAME]
    device_info = config[ATTR_DEVICE_INFO]

    tv_device = PanasonicVieraTVEntity(remote, name, device_info)
    async_add_entities([tv_device])


class PanasonicVieraTVEntity(MediaPlayerEntity):
    """Representation of a Panasonic Viera TV."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )

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
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        if self._device_info is None:
            return None
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_info[ATTR_UDN])},
            manufacturer=self._device_info.get(ATTR_MANUFACTURER, DEFAULT_MANUFACTURER),
            model=self._device_info.get(ATTR_MODEL_NUMBER, DEFAULT_MODEL_NUMBER),
            name=self._name,
        )

    @property
    def device_class(self):
        """Return the device class of the device."""
        return MediaPlayerDeviceClass.TV

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
        if media_source.is_media_source_id(media_id):
            media_type = MEDIA_TYPE_URL
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = play_item.url

        if media_type != MEDIA_TYPE_URL:
            _LOGGER.warning("Unsupported media_type: %s", media_type)
            return

        media_id = async_process_play_media_url(self.hass, media_id)
        await self._remote.async_play_media(media_type, media_id)

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(self.hass, media_content_id)
