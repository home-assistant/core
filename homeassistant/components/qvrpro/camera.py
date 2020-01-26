"""
Support for viewing camera streams from QVR Pro.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.qvrpro
"""

from homeassistant.components.camera import Camera

from .const import DOMAIN


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the QVR Pro camera platform."""
    if discovery_info is None:
        return

    client = hass.data[DOMAIN]["client"]

    entities = []

    for channel in hass.data[DOMAIN]["channels"]:
        entities.append(QVRProCamera(channel, client))

    add_entities(entities)


class QVRProCamera(Camera):
    """Representation of a QVR Pro camera."""

    def __init__(self, channel, client):
        """Init QVR Pro camera."""

        self._channel = channel
        self._client = client

        super().__init__()

    @property
    def name(self):
        """Get the name of the camera."""
        return self._channel.name

    @property
    def model(self):
        """Get the model of the camera."""
        return self._channel.model

    @property
    def brand(self):
        """Get the brand of the camera."""
        return self._channel.brand

    @property
    def state_attributes(self):
        """Get the state attributes."""
        attrs = super().state_attributes

        attrs["qvr_guid"] = self._channel.guid

        return attrs

    def camera_image(self):
        """Get image bytes from camera."""
        return self._client.get_snapshot(self._channel.guid)
