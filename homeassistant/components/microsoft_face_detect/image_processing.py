"""Component that will help set the Microsoft face detect processing."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.image_processing import (
    ATTR_AGE,
    ATTR_GENDER,
    ATTR_GLASSES,
    PLATFORM_SCHEMA as IMAGE_PROCESSING_PLATFORM_SCHEMA,
    FaceInformation,
    ImageProcessingFaceEntity,
)
from homeassistant.components.microsoft_face import DATA_MICROSOFT_FACE, MicrosoftFace
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_SOURCE
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

SUPPORTED_ATTRIBUTES = [ATTR_AGE, ATTR_GENDER, ATTR_GLASSES]

CONF_ATTRIBUTES = "attributes"
DEFAULT_ATTRIBUTES = [ATTR_AGE, ATTR_GENDER]


def validate_attributes(list_attributes):
    """Validate face attributes."""
    for attr in list_attributes:
        if attr not in SUPPORTED_ATTRIBUTES:
            raise vol.Invalid(f"Invalid attribute {attr}")
    return list_attributes


PLATFORM_SCHEMA = IMAGE_PROCESSING_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ATTRIBUTES, default=DEFAULT_ATTRIBUTES): vol.All(
            cv.ensure_list, validate_attributes
        )
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Microsoft Face detection platform."""
    api = hass.data[DATA_MICROSOFT_FACE]
    attributes: list[str] = config[CONF_ATTRIBUTES]
    source: list[dict[str, str]] = config[CONF_SOURCE]

    async_add_entities(
        MicrosoftFaceDetectEntity(
            camera[CONF_ENTITY_ID], api, attributes, camera.get(CONF_NAME)
        )
        for camera in source
    )


class MicrosoftFaceDetectEntity(ImageProcessingFaceEntity):
    """Microsoft Face API entity for identify."""

    def __init__(
        self,
        camera_entity: str,
        api: MicrosoftFace,
        attributes: list[str],
        name: str | None,
    ) -> None:
        """Initialize Microsoft Face."""
        super().__init__()

        self._api = api
        self._attr_camera_entity = camera_entity
        self._attributes = attributes

        if name:
            self._attr_name = name
        else:
            self._attr_name = f"MicrosoftFace {split_entity_id(camera_entity)[1]}"

    async def async_process_image(self, image: bytes) -> None:
        """Process image.

        This method is a coroutine.
        """
        face_data = None
        try:
            face_data = await self._api.call_api(
                "post",
                "detect",
                image,
                binary=True,
                params={"returnFaceAttributes": ",".join(self._attributes)},
            )

        except HomeAssistantError as err:
            _LOGGER.error("Can't process image on microsoft face: %s", err)
            return

        if not face_data:
            face_data = []

        faces: list[FaceInformation] = []
        for face in face_data:
            face_attr = FaceInformation()
            for attr in self._attributes:
                if TYPE_CHECKING:
                    assert attr in SUPPORTED_ATTRIBUTES
                if attr in face["faceAttributes"]:
                    face_attr[attr] = face["faceAttributes"][attr]  # type: ignore[literal-required]

            if face_attr:
                faces.append(face_attr)

        self.async_process_faces(faces, len(face_data))
