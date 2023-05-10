"""Support for the QR code image processing."""
from __future__ import annotations

import io

from PIL import Image
from pyzbar import pyzbar

from homeassistant.components.image_processing import ImageProcessingEntity
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_SOURCE
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the QR code image processing platform."""
    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(QrEntity(camera[CONF_ENTITY_ID], camera.get(CONF_NAME)))

    add_entities(entities)


class QrEntity(ImageProcessingEntity):
    """A QR image processing entity."""

    def __init__(self, camera_entity, name):
        """Initialize QR image processing entity."""
        super().__init__()

        self._camera = camera_entity
        if name:
            self._name = name
        else:
            self._name = f"QR {split_entity_id(camera_entity)[1]}"
        self._state = None

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    def process_image(self, image):
        """Process image."""
        stream = io.BytesIO(image)
        img = Image.open(stream)

        barcodes = pyzbar.decode(img)
        if barcodes:
            self._state = barcodes[0].data.decode("utf-8")
        else:
            self._state = None
