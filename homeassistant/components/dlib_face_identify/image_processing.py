"""Component that will help set the Dlib face detect processing."""
import asyncio
import imghdr
import io
import logging
import pathlib

# pylint: disable=import-error
import face_recognition
import voluptuous as vol

from homeassistant.components.image_processing import (
    CONF_CONFIDENCE,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_SOURCE,
    PLATFORM_SCHEMA,
    ImageProcessingFaceEntity,
)
from homeassistant.core import callback, split_entity_id
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_NAME = "name"
ATTR_DISTANCE = "distance"
CONF_FACES = "faces"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_FACES): vol.Any({cv.string: cv.isfile}, cv.isdir),
        vol.Optional(CONF_CONFIDENCE, default=0.6): vol.Coerce(float),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Dlib Face detection platform."""
    entities = []

    face_encodings_task = hass.async_create_task(
        async_generate_encodings(hass, config[CONF_FACES])
    )

    for camera in config[CONF_SOURCE]:

        entity = DlibFaceIdentifyEntity(
            camera[CONF_ENTITY_ID],
            face_encodings_task,
            camera.get(CONF_NAME),
            config[CONF_CONFIDENCE],
        )

        entities.append(entity)

    async_add_entities(entities)


async def async_generate_encodings(hass, faces):
    """Generate face encodings."""
    face_encodings = {}

    if not isinstance(faces, dict):
        faces_root_path = pathlib.Path(faces)
        if not faces_root_path.is_dir():
            _LOGGER.error(
                "Path '%s' does not exist or is not a valid directory. No face encodings generated",
                faces_root_path.resolve(),
            )
            return face_encodings

        face_directories = [
            faces_root_path / n for n in faces_root_path.iterdir() if n.is_dir()
        ]

        for face_images in face_directories:
            face_encodings[face_images.stem] = []

            for face_file in [
                face_images / i for i in face_images.iterdir() if i.is_file()
            ]:
                if imghdr.what(face_file) is None:
                    continue

                encoded_known_face = await async_extract_face_encoding(hass, face_file)

                if encoded_known_face is not None:
                    face_encodings[face_images.stem].append(encoded_known_face)

    else:

        for face_name, face_file in faces.items():
            encoded_known_face = await async_extract_face_encoding(hass, face_file)

            if encoded_known_face is None:
                continue

            if face_name in face_encodings:
                face_encodings[face_name].append(encoded_known_face)
            else:
                face_encodings[face_name] = [encoded_known_face]

    return face_encodings


async def async_extract_face_encoding(hass, face_file):
    """Extract face encoding from an image."""
    try:
        image = await hass.async_add_executor_job(
            face_recognition.load_image_file, face_file
        )

        encodings_list = await hass.async_add_executor_job(
            face_recognition.face_encodings, image
        )

        if len(encodings_list) > 1:
            _LOGGER.error(
                "Failed to parse %s. More than one face detected in image for a known person",
                face_file,
            )
            return None

        return encodings_list[0]

    except IndexError as err:
        _LOGGER.error("Failed to parse %s. Error: %s", face_file, err)
        return None


class DlibFaceIdentifyEntity(ImageProcessingFaceEntity):
    """Dlib Face API entity for identify."""

    def __init__(self, camera_entity, face_encodings_task, name, tolerance):
        """Initialize Dlib face identify entry."""
        super().__init__()

        self._camera = camera_entity

        if name:
            self._name = name
        else:
            self._name = f"Dlib Face {split_entity_id(camera_entity)[1]}"

        self._faces = {}
        face_encodings_task.add_done_callback(self.async_encodings_ready)
        self._tolerance = tolerance

    @callback
    def async_encodings_ready(self, future):
        """Update known face encodings when the task has finished."""
        try:
            encodings = future.result()

            for name, face_encoding_list in encodings.items():
                self._faces[name] = face_encoding_list

        except asyncio.InvalidStateError:
            _LOGGER.error("Generating known face encodings failed")

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    def process_image(self, image):
        """Process image."""
        fak_file = io.BytesIO(image)
        fak_file.name = "snapshot.jpg"
        fak_file.seek(0)

        image = face_recognition.load_image_file(fak_file)
        unknowns = face_recognition.face_encodings(image)

        found = []
        for unknown_face in unknowns:

            closest_match = None
            smallest_average_distance = None

            for name, known_encodings in self._faces.items():
                distances = face_recognition.face_distance(
                    known_encodings, unknown_face
                )
                average_distance = 0

                for i in distances:
                    average_distance += i

                average_distance = average_distance / len(known_encodings)

                if average_distance < self._tolerance:
                    if (
                        smallest_average_distance is None
                        or average_distance < smallest_average_distance
                    ):
                        smallest_average_distance = average_distance
                        closest_match = name

            if closest_match is not None:
                found.append(
                    {ATTR_DISTANCE: smallest_average_distance, ATTR_NAME: closest_match}
                )

        self.process_faces(found, len(unknowns))
