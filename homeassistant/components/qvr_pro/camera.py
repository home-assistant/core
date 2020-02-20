"""Support for QVR Pro streams."""

from homeassistant.components.camera import SUPPORT_STREAM, Camera

from .const import DOMAIN, SHORT_NAME


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the QVR Pro camera platform."""
    if discovery_info is None:
        return

    client = hass.data[DOMAIN]["client"]

    entities = []

    for channel in hass.data[DOMAIN]["channels"]:
        entities.append(QVRProCamera(**channel, client=client))

    add_entities(entities)


class QVRProCamera(Camera):
    """Representation of a QVR Pro camera."""

    def __init__(self, name, model, brand, channel_index, guid, client):
        """Init QVR Pro camera."""

        self.name = f"{SHORT_NAME} {name}"
        self.model = model
        self.brand = brand
        self.index = channel_index
        self.guid = guid
        self._client = client

        super().__init__()

    @property
    def device_state_attributes(self):
        """Get the state attributes."""
        attrs = {"qvr_guid": self.guid}

        return attrs

    def camera_image(self):
        """Get image bytes from camera."""
        return self._client.get_snapshot(self.guid)

    def stream_source(self):
        """Get stream source."""
        return self._client.get_channel_live_stream(self.guid)

    @property
    def supported_features(self):
        """Get supported features."""
        return SUPPORT_STREAM
