"""
Support for viewing camera streams from QVR Pro

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.qvrpro
"""

from homeassistant.components.camera import Camera
from homeassistant.components.qvrpro import DOMAIN as QVRPRO_DOMAIN

DEPENDENCIES = ['qvrpro']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the QVR Pro camera platform."""

    client = hass.data[QVRPRO_DOMAIN]['client']

    entities = []

    for channel in hass.data[QVRPRO_DOMAIN]['channels']:
        entities.append(QVRProCamera(channel, client))

    async_add_entities(entities)


class QVRProCamera(Camera):
    """Representation of a QVR Pro camera"""

    def __init__(self, channel, client):
        """Init QVR Pro camera."""

        self._channel = channel
        self._client = client

        super().__init__()

    @property
    def name(self):
        """Get the name of the camera."""
        return self._channel.name

    def camera_image(self):
        """Get image bytes from camera."""
        return self._client.get_snapshot(self._channel.guid)

    @property
    def brand(self):
        """Get the camera brand."""
        return self._channel.brand
