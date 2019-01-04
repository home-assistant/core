"""
Support for controlling what images are displayed on the Depict art frame.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.depict/
"""

from homeassistant.components.media_player import (
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_PLAY_MEDIA, MediaPlayerDevice)
from homeassistant.const import (STATE_ON, STATE_OFF)
from ..depict import CONF_NAME, DATA_DEPICT

DEPENDENCIES = ['depict']

SUPPORTED_FEATURES = SUPPORT_TURN_OFF \
    | SUPPORT_TURN_ON \
    | SUPPORT_PLAY_MEDIA

ATTR_ORIENTATION = 'orientation'
ATTR_RESOLUTION = 'resolution'
MEDIA_TYPE_IMAGE = 'image'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a media player entity for a Depict frame."""
    name = discovery_info[CONF_NAME]
    add_entities(
        [DepictMediaPlayer(name, hass.data[DATA_DEPICT][name])],
        update_before_add=True)


class DepictMediaPlayer(MediaPlayerDevice):
    """Represents a Depict art frame as a media player."""

    def __init__(self, name, frame):
        """Initialize the Depict media device."""
        self._name = name
        self._frame = frame
        self._url = None

    @property
    def supported_features(self):
        """Return the features supported by this frame."""
        return SUPPORTED_FEATURES

    @property
    def name(self):
        """Return the name of the frame."""
        return self._name

    @property
    def state(self):
        """Return the current state of the frame."""
        if self._frame.is_on:
            return STATE_ON

        return STATE_OFF

    @property
    def device_state_attributes(self):
        """Return other details about the device."""
        return {
            ATTR_ORIENTATION: self._frame.orientation,
            ATTR_RESOLUTION: self._frame.resolution,
        }

    @property
    def media_content_type(self):
        """Return the content type currently displaying; i.e. an image."""
        return MEDIA_TYPE_IMAGE

    @property
    def media_content_id(self):
        """Return the URL for the image being displayed."""
        return self._url

    @property
    def media_image_url(self):
        """Return the URL for the image being displayed."""
        return self._url

    async def async_turn_off(self):
        """Turn the frame off."""
        if self._frame.is_on:
            await self._frame.sleep()

    async def async_turn_on(self):
        """Turn the frame on."""
        if not self._frame.is_on:
            await self._frame.wakeup()

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Display an image."""
        self._url = media_id
        await self._frame.set_image_url(media_id)
