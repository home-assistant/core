"""AWS platform for notify component."""
import asyncio
import base64
import json
import logging

import aiobotocore
import botocore.exceptions


from homeassistant.components.image_processing import (
    ATTR_CONFIDENCE,
    ATTR_NAME,
    CONF_CONFIDENCE,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_SOURCE,
    PLATFORM_SCHEMA,
    ImageProcessingFaceEntity,
)
from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.helpers.json import JSONEncoder
from homeassistant.core import split_entity_id

from .const import (
    CONF_COLLECTION_ID,
    CONF_CONTEXT,
    CONF_CREDENTIAL_NAME,
    CONF_PROFILE_NAME,
    CONF_REGION,
    CONF_SERVICE,
    DATA_SESSIONS,
)

_LOGGER = logging.getLogger(__name__)


async def get_available_regions(hass, service):
    """Get available regions for a service."""

    session = aiobotocore.get_session()
    # get_available_regions is not a coroutine since it does not perform
    # network I/O. But it still perform file I/O heavily, so put it into
    # an executor thread to unblock event loop
    return await hass.async_add_executor_job(session.get_available_regions, service)


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Get the Rekognition image processing platform."""
    if discovery_info is None:
        _LOGGER.error("Please config aws notify platform in aws component")
        return None

    session = None

    conf = discovery_info

    service = conf[CONF_SERVICE]
    region_name = conf[CONF_REGION]
    session_config = {CONF_REGION: conf[CONF_REGION]}

    available_regions = await get_available_regions(hass, service)
    if region_name not in available_regions:
        _LOGGER.error(
            "Region %s is not available for %s service, must in %s",
            region_name,
            service,
            available_regions,
        )
        return None

    aws_config = conf.copy()
    if CONF_CREDENTIAL_NAME in aws_config:
        credential_name = aws_config.get(CONF_CREDENTIAL_NAME)
        if credential_name is not None:
            session = hass.data[DATA_SESSIONS].get(credential_name)
            if session is None:
                _LOGGER.warning("No available aws session for %s", credential_name)
            del aws_config[CONF_CREDENTIAL_NAME]
    elif CONF_PROFILE_NAME in aws_config:
        profile = aws_config.get(CONF_PROFILE_NAME)
        if profile is not None:
            session = aiobotocore.AioSession(profile=profile)
            del aws_config[CONF_PROFILE_NAME]
    else:
        # no platform config, use the first aws component credential instead
        if hass.data[DATA_SESSIONS]:
            session = next(iter(hass.data[DATA_SESSIONS].values()))
        else:
            _LOGGER.error("Missing aws credential for %s", config[CONF_NAME])
            return None
    if session is None:
        session = aiobotocore.AioSession()

    collection_id = conf.get(CONF_COLLECTION_ID, "collection")
    confidence = conf.get(CONF_CONFIDENCE, 70)

    if service == "rekognition":
        entities = []
        for camera in conf.get(CONF_SOURCE, []):
            face_entity = RekognitionSearchFaceEntity(
                camera[CONF_ENTITY_ID],
                session,
                session_config,
                collection_id,
                confidence,
                camera.get(CONF_NAME),
            )
            entities.append(face_entity)
        add_entities(entities)
    return None


class RekognitionSearchFaceEntity(ImageProcessingFaceEntity):
    """Representation of the Microsoft Face API entity for identify."""

    _service = "rekognition"

    def __init__(
        self,
        camera_entity,
        session,
        session_config,
        collection_id,
        confidence,
        name=None,
    ):
        """Initialize the Microsoft Face API."""
        super().__init__()

        self._session = session
        self._session_config = session_config
        self._camera = camera_entity
        self._confidence = confidence
        self._collection_id = collection_id

        if name:
            self._name = name
        else:
            self._name = f"Rekognition Face {split_entity_id(camera_entity)[1]}"

    @property
    def confidence(self):
        """Return minimum confidence for send events."""
        return self._confidence

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    async def async_process_image(self, image):
        """Process image.

        This method is a coroutine.
        """
        async with self._session.create_client(
            self._service, **self._session_config
        ) as client:
            try:
                search_image = await client.search_faces_by_image(
                    CollectionId=self._collection_id,
                    Image={"Bytes": image},
                    FaceMatchThreshold=self._confidence,
                    MaxFaces=1,
                )
            except client.exceptions.InvalidParameterException as e:
                _LOGGER.error("No faces detected")
                self.async_process_faces([], 0)
                return None
            known_faces = []
            _LOGGER.error("Data: %s", search_image)
            matches = search_image["FaceMatches"]
            for match in search_image["FaceMatches"]:
                _LOGGER.error("Face detected: %s", match)
                image_id = match["Face"]["ExternalImageId"]
                match_confidence = match["Face"]["Confidence"]
                match_name = image_id.split("_")[0]
                known_faces.append(
                    {ATTR_NAME: match_name, ATTR_CONFIDENCE: match_confidence}
                )
            self.async_process_faces(known_faces, len(matches))
