"""Provides functionality to interact with image processing services."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from enum import StrEnum
import logging
from typing import Any, Final, TypedDict, final

import voluptuous as vol

from homeassistant.components.camera import async_get_image
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NAME,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_SOURCE,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import make_entity_service_schema
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "image_processing"
SCAN_INTERVAL = timedelta(seconds=10)


class ImageProcessingDeviceClass(StrEnum):
    """Device class for image processing entities."""

    # Automatic license plate recognition
    ALPR = "alpr"

    # Face
    FACE = "face"

    # OCR
    OCR = "ocr"


SERVICE_SCAN = "scan"

EVENT_DETECT_FACE = "image_processing.detect_face"

ATTR_AGE = "age"
ATTR_CONFIDENCE: Final = "confidence"
ATTR_FACES = "faces"
ATTR_GENDER = "gender"
ATTR_GLASSES = "glasses"
ATTR_MOTION: Final = "motion"
ATTR_TOTAL_FACES = "total_faces"

CONF_CONFIDENCE = "confidence"

DEFAULT_TIMEOUT = 10
DEFAULT_CONFIDENCE = 80

SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_domain("camera"),
        vol.Optional(CONF_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_SOURCE): vol.All(cv.ensure_list, [SOURCE_SCHEMA]),
        vol.Optional(CONF_CONFIDENCE, default=DEFAULT_CONFIDENCE): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=100)
        ),
    }
)
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE.extend(PLATFORM_SCHEMA.schema)


class FaceInformation(TypedDict, total=False):
    """Face information."""

    confidence: float
    name: str
    age: float
    gender: str
    motion: str
    glasses: str
    entity_id: str


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the image processing."""
    component = EntityComponent[ImageProcessingEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    async def async_scan_service(service: ServiceCall) -> None:
        """Service handler for scan."""
        image_entities = await component.async_extract_from_service(service)

        update_tasks = []
        for entity in image_entities:
            entity.async_set_context(service.context)
            update_tasks.append(asyncio.create_task(entity.async_update_ha_state(True)))

        if update_tasks:
            await asyncio.wait(update_tasks)

    hass.services.async_register(
        DOMAIN, SERVICE_SCAN, async_scan_service, schema=make_entity_service_schema({})
    )

    return True


class ImageProcessingEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes sensor entities."""

    device_class: ImageProcessingDeviceClass | None = None
    camera_entity: str | None = None
    confidence: float | None = None


class ImageProcessingEntity(Entity):
    """Base entity class for image processing."""

    entity_description: ImageProcessingEntityDescription
    _attr_device_class: ImageProcessingDeviceClass | None
    _attr_camera_entity: str | None
    _attr_confidence: float | None
    timeout = DEFAULT_TIMEOUT

    @property
    def camera_entity(self) -> str | None:
        """Return camera entity id from process pictures."""
        if hasattr(self, "_attr_camera_entity"):
            return self._attr_camera_entity
        if hasattr(self, "entity_description"):
            return self.entity_description.camera_entity
        return None

    @property
    def confidence(self) -> float | None:
        """Return minimum confidence to do some things."""
        if hasattr(self, "_attr_confidence"):
            return self._attr_confidence
        if hasattr(self, "entity_description"):
            return self.entity_description.confidence
        return None

    @property
    def device_class(self) -> ImageProcessingDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    def process_image(self, image: bytes) -> None:
        """Process image."""
        raise NotImplementedError

    async def async_process_image(self, image: bytes) -> None:
        """Process image."""
        return await self.hass.async_add_executor_job(self.process_image, image)

    async def async_update(self) -> None:
        """Update image and process it.

        This method is a coroutine.
        """
        if self.camera_entity is None:
            _LOGGER.error(
                "No camera entity id was set by the image processing entity",
            )
            return

        try:
            image = await async_get_image(
                self.hass, self.camera_entity, timeout=self.timeout
            )
        except HomeAssistantError as err:
            _LOGGER.error("Error on receive image from entity: %s", err)
            return

        # process image data
        await self.async_process_image(image.content)


class ImageProcessingFaceEntity(ImageProcessingEntity):
    """Base entity class for face image processing."""

    _attr_device_class = ImageProcessingDeviceClass.FACE

    def __init__(self) -> None:
        """Initialize base face identify/verify entity."""
        self.faces: list[FaceInformation] = []
        self.total_faces = 0

    @property
    def state(self) -> str | int | None:
        """Return the state of the entity."""
        confidence: float = 0
        state = None

        # No confidence support
        if not self.confidence:
            return self.total_faces

        # Search high confidence
        for face in self.faces:
            if ATTR_CONFIDENCE not in face:
                continue

            if (f_co := face[ATTR_CONFIDENCE]) > confidence:
                confidence = f_co
                for attr in (ATTR_NAME, ATTR_MOTION):
                    if attr in face:
                        state = face[attr]
                        break

        return state

    @final
    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return {ATTR_FACES: self.faces, ATTR_TOTAL_FACES: self.total_faces}

    def process_faces(self, faces: list[FaceInformation], total: int) -> None:
        """Send event with detected faces and store data."""
        self.hass.loop.call_soon_threadsafe(self.async_process_faces, faces, total)

    @callback
    def async_process_faces(self, faces: list[FaceInformation], total: int) -> None:
        """Send event with detected faces and store data.

        known are a dict in follow format:
         [
           {
              ATTR_CONFIDENCE: 80,
              ATTR_NAME: 'Name',
              ATTR_AGE: 12.0,
              ATTR_GENDER: 'man',
              ATTR_MOTION: 'smile',
              ATTR_GLASSES: 'sunglasses'
           },
         ]

        This method must be run in the event loop.
        """
        # Send events
        for face in faces:
            if (
                ATTR_CONFIDENCE in face
                and self.confidence
                and face[ATTR_CONFIDENCE] < self.confidence
            ):
                continue

            face.update({ATTR_ENTITY_ID: self.entity_id})
            self.hass.bus.async_fire(EVENT_DETECT_FACE, face)

        # Update entity store
        self.faces = faces
        self.total_faces = total
