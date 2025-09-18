"""Component that will help set the Microsoft face for verify processing."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.image_processing import (
    ATTR_CONFIDENCE,
    CONF_CONFIDENCE,
    PLATFORM_SCHEMA as IMAGE_PROCESSING_PLATFORM_SCHEMA,
    FaceInformation,
    ImageProcessingFaceEntity,
)
from homeassistant.components.microsoft_face import DATA_MICROSOFT_FACE, MicrosoftFace
from homeassistant.const import ATTR_NAME, CONF_ENTITY_ID, CONF_NAME, CONF_SOURCE
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_GROUP = "group"

PLATFORM_SCHEMA = IMAGE_PROCESSING_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_GROUP): cv.slugify}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Microsoft Face identify platform."""
    api = hass.data[DATA_MICROSOFT_FACE]
    face_group: str = config[CONF_GROUP]
    confidence: float = config[CONF_CONFIDENCE]
    source: list[dict[str, str]] = config[CONF_SOURCE]

    async_add_entities(
        MicrosoftFaceIdentifyEntity(
            camera[CONF_ENTITY_ID],
            api,
            face_group,
            confidence,
            camera.get(CONF_NAME),
        )
        for camera in source
    )


class MicrosoftFaceIdentifyEntity(ImageProcessingFaceEntity):
    """Representation of the Microsoft Face API entity for identify."""

    def __init__(
        self,
        camera_entity: str,
        api: MicrosoftFace,
        face_group: str,
        confidence: float,
        name: str | None,
    ) -> None:
        """Initialize the Microsoft Face API."""
        super().__init__()

        self._api = api
        self._attr_camera_entity = camera_entity
        self._attr_confidence = confidence
        self._face_group = face_group

        if name:
            self._attr_name = name
        else:
            self._attr_name = f"MicrosoftFace {split_entity_id(camera_entity)[1]}"

    async def async_process_image(self, image: bytes) -> None:
        """Process image.

        This method is a coroutine.
        """
        detect = []
        try:
            face_data = await self._api.call_api("post", "detect", image, binary=True)

            if face_data:
                face_ids = [data["faceId"] for data in face_data]
                detect = await self._api.call_api(
                    "post",
                    "identify",
                    {"faceIds": face_ids, "personGroupId": self._face_group},
                )

        except HomeAssistantError as err:
            _LOGGER.error("Can't process image on Microsoft face: %s", err)
            return

        # Parse data
        known_faces: list[FaceInformation] = []
        total = 0
        for face in detect:
            total += 1
            if not face["candidates"]:
                continue

            data = face["candidates"][0]
            name = ""
            for s_name, s_id in self._api.store[self._face_group].items():
                if data["personId"] == s_id:
                    name = s_name
                    break

            known_faces.append(
                {ATTR_NAME: name, ATTR_CONFIDENCE: data["confidence"] * 100}
            )

        self.async_process_faces(known_faces, total)
