"""Support for QVR Pro streams."""
from __future__ import annotations

import logging

from pyqvrpro.client import QVRResponseError

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, SHORT_NAME

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the QVR Pro camera platform."""
    if discovery_info is None:
        return

    client = hass.data[DOMAIN]["client"]

    entities = []

    for channel in hass.data[DOMAIN]["channels"]:

        stream_source = get_stream_source(channel["guid"], client)
        entities.append(
            QVRProCamera(**channel, stream_source=stream_source, client=client)
        )

    add_entities(entities)


def get_stream_source(guid, client):
    """Get channel stream source."""
    try:
        resp = client.get_channel_live_stream(guid, protocol="rtsp")

        full_url = resp["resourceUris"]

        protocol = full_url[:7]
        auth = f"{client.get_auth_string()}@"
        url = full_url[7:]

        return f"{protocol}{auth}{url}"

    except QVRResponseError as ex:
        _LOGGER.error(ex)
        return None


class QVRProCamera(Camera):
    """Representation of a QVR Pro camera."""

    def __init__(self, name, model, brand, channel_index, guid, stream_source, client):
        """Init QVR Pro camera."""

        self._name = f"{SHORT_NAME} {name}"
        self._model = model
        self._brand = brand
        self.index = channel_index
        self.guid = guid
        self._client = client
        self._stream_source = stream_source

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
    def extra_state_attributes(self):
        """Get the state attributes."""
        attrs = {"qvr_guid": self.guid}

        return attrs

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Get image bytes from camera."""
        try:
            return self._client.get_snapshot(self.guid)

        except QVRResponseError as ex:
            _LOGGER.error("Error getting image: %s", ex)
            self._client.connect()

        return self._client.get_snapshot(self.guid)

    async def stream_source(self):
        """Get stream source."""
        return self._stream_source
