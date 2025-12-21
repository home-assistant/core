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
    source: list[dict[str, str]] = config[CONF_SOURCE]
    add_entities(
        QrEntity(camera[CONF_ENTITY_ID], camera.get(CONF_NAME)) for camera in source
    )


class QrEntity(ImageProcessingEntity):
    """A QR image processing entity."""

    def __init__(self, camera_entity: str, name: str | None) -> None:
        """Initialize QR image processing entity."""
        super().__init__()

        self._attr_camera_entity = camera_entity
        if name:
            self._attr_name = name
        else:
            self._attr_name = f"QR {split_entity_id(camera_entity)[1]}"
        self._attr_state = None

    def process_image(self, image: bytes) -> None:
        """Process image."""
        stream = io.BytesIO(image)
        img = Image.open(stream)

        barcodes = pyzbar.decode(img)
        if barcodes:
            self._attr_state = barcodes[0].data.decode("utf-8")
        else:
            self._attr_state = None
