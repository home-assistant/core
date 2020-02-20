"""Support for QVR Pro streams."""

import logging

from pyqvrpro.client import QVRResponseError

from homeassistant.components.camera import SUPPORT_STREAM, Camera

from .const import DOMAIN, SHORT_NAME

_LOGGER = logging.getLogger(__name__)


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

        self._name = f"{SHORT_NAME} {name}"
        self._model = model
        self._brand = brand
        self.index = channel_index
        self.guid = guid
        self._client = client

        try:
            self._stream_source = self._client.get_channel_live_stream(guid)
        except QVRResponseError as e:
            self._stream_source = None
            _LOGGER.error(e)

        self._supported_features = SUPPORT_STREAM if self._stream_source else 0

        super().__init__()

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def model(self):
        """Return the model of the entity."""
        return self._model

    @property
    def brand(self):
        """Return the brand of the entity."""
        return self._brand

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
        return self._stream_source

    @property
    def supported_features(self):
        """Get supported features."""
        return self._supported_features
