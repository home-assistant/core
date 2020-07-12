"""AWS platform for image_processing component."""
import io
import logging
import re

from PIL import Image, ImageDraw, UnidentifiedImageError
import aiobotocore

from homeassistant.components.image_processing import (
    ATTR_AGE,
    ATTR_CONFIDENCE,
    ATTR_GENDER,
    ATTR_GLASSES,
    ATTR_MOTION,
    ATTR_NAME,
    CONF_CONFIDENCE,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_SOURCE,
    ImageProcessingEntity,
    ImageProcessingFaceEntity,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM
from homeassistant.core import split_entity_id
import homeassistant.util.dt as dt_util
from homeassistant.util.pil import draw_box

from .const import (
    ATTR_LABELS,
    ATTR_OBJECTS,
    CONF_ACCESS_KEY_ID,
    CONF_COLLECTION_ID,
    CONF_CREDENTIAL_NAME,
    CONF_DETECTION_ATTRIBUTES,
    CONF_IDENTIFY_FACES,
    CONF_PROFILE_NAME,
    CONF_REGION,
    CONF_SAVE_FILE_FOLDER,
    CONF_SAVE_FILE_TIMESTAMP,
    CONF_SECRET_ACCESS_KEY,
    CONF_SERVICE,
    DATA_SESSIONS,
    EVENT_LABEL_DETECTED,
    EVENT_OBJECT_DETECTED,
)

_LOGGER = logging.getLogger(__name__)

DATETIME_FORMAT = "%Y-%m-%d_%H:%M:%S"
SCAN_INTERVAL = dt_util.dt.timedelta(weeks=52)


def get_valid_filename(name: str) -> str:
    """Parse input to ensure valid filename characters."""
    return re.sub(r"(?u)[^-\w.]", "", str(name).strip().replace(" ", "_"))


def save_image(self, image, entity_name, objects, directory, save_timestamp=False):
    """Draw the bounding boxes and save the image."""
    try:
        img = Image.open(io.BytesIO(bytearray(image))).convert("RGB")
    except UnidentifiedImageError:
        _LOGGER.warning("Rekognition unable to process image, bad data")
        return
    draw = ImageDraw.Draw(img)
    for obj in objects:
        name = obj["name"]
        confidence = obj["confidence"]
        box = obj["bounding_box"]
        centroid = obj["centroid"]
        box_colour = (255, 255, 0)  # Yellow
        box_label = f"{name}: {confidence:.1f}%"
        draw_box(
            draw,
            (box["y_min"], box["x_min"], box["y_max"], box["x_max"]),
            img.width,
            img.height,
            text=box_label,
            color=box_colour,
        )
        # draw bullseye
        draw.text(
            (centroid["x"] * img.width, centroid["y"] * img.height),
            text="X",
            fill=box_colour,
        )
    filename = get_valid_filename(entity_name).lower()
    latest_save_path = f"{directory}/{filename}_latest.jpg"
    img.save(latest_save_path)
    if save_timestamp:
        timestamp = dt_util.now().strftime(DATETIME_FORMAT)
        timestamp_save_path = f"{directory}/{filename}_{timestamp}.jpg"
        img.save(timestamp_save_path)
        _LOGGER.info("Rekognition saved file %s", timestamp_save_path)


def compute_box(box, decimal_places):
    """Compute AWS BoundingBox coordinates to be PIL compatible."""
    box_data = {}
    # Get bounding box
    x_min, y_min, width, height = (
        box["Left"],
        box["Top"],
        box["Width"],
        box["Height"],
    )
    x_max, y_max = x_min + width, y_min + height

    box_data["bounding_box"] = {
        "x_min": round(x_min, decimal_places),
        "y_min": round(y_min, decimal_places),
        "x_max": round(x_max, decimal_places),
        "y_max": round(y_max, decimal_places),
        "width": round(box["Width"], decimal_places),
        "height": round(box["Height"], decimal_places),
    }

    # Get box area (% of frame)
    box_data["box_area"] = round((width * height * 100), decimal_places)

    # Get box centroid
    centroid_x, centroid_y = (x_min + width / 2), (y_min + height / 2)
    box_data["centroid"] = {
        "x": round(centroid_x, decimal_places),
        "y": round(centroid_y, decimal_places),
    }
    return box_data


def get_objects(response, confidence):
    """Parse the data, returning detected objects only."""
    objects = []
    labels = []
    decimal_places = 3

    for label in response["Labels"]:
        if len(label["Instances"]) > 0:
            for instance in label["Instances"]:
                if instance["Confidence"] < confidence:
                    continue
                # Extract and format instance data
                box = instance["BoundingBox"]
                box_data = compute_box(box, decimal_places)
                box_data.update(
                    {
                        "name": label["Name"].lower(),
                        "confidence": round(instance["Confidence"], decimal_places),
                    }
                )
                objects.append(box_data)
        else:
            if label["Confidence"] < confidence:
                continue
            label_info = {
                "name": label["Name"].lower(),
                "confidence": round(label["Confidence"], decimal_places),
            }
            labels.append(label_info)
    return objects, labels


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
    platform = conf[CONF_PLATFORM]
    region_name = conf[CONF_REGION]
    session_config = {CONF_REGION: conf[CONF_REGION]}
    platform = conf[CONF_PLATFORM]

    available_regions = await get_available_regions(hass, service)
    if region_name not in available_regions:
        _LOGGER.error(
            "Region %s is not available for %s service, must in %s",
            region_name,
            service,
            available_regions,
        )
        return None

    platform_config = False
    if CONF_SECRET_ACCESS_KEY in conf:
        platform_config = True
        session_config[CONF_ACCESS_KEY_ID] = conf[CONF_ACCESS_KEY_ID]
        session_config[CONF_SECRET_ACCESS_KEY] = conf[CONF_SECRET_ACCESS_KEY]
        del conf[CONF_ACCESS_KEY_ID]
        del conf[CONF_SECRET_ACCESS_KEY]
    if CONF_CREDENTIAL_NAME in conf:
        platform_config = True
    if CONF_PROFILE_NAME in conf:
        platform_config = True

    if not platform_config:
        # no platform config, use the first aws component credential instead
        if hass.data[DATA_SESSIONS]:
            session = next(iter(hass.data[DATA_SESSIONS].values()))
        else:
            _LOGGER.error("Missing aws credential for %s", config[CONF_NAME])
            return None

    if session is None:
        credential_name = conf.get(CONF_CREDENTIAL_NAME)
        if credential_name is not None:
            session = hass.data[DATA_SESSIONS].get(credential_name)
            if session is None:
                _LOGGER.warning("No available aws session for %s", credential_name)
            del conf[CONF_CREDENTIAL_NAME]

    if session is None:
        profile = conf.get(CONF_PROFILE_NAME)
        if profile is not None:
            session = aiobotocore.AioSession(profile=profile)
            del conf[CONF_PROFILE_NAME]
        else:
            session = aiobotocore.AioSession()

    if platform == "face":
        entities = []
        for camera in conf.get(CONF_SOURCE, []):
            face_entity = RekognitionFaceEntity(
                camera[CONF_ENTITY_ID],
                session,
                session_config,
                conf,
                camera.get(CONF_NAME),
            )
            entities.append(face_entity)
        add_entities(entities)
    if platform == "object":
        entities = []
        for camera in conf.get(CONF_SOURCE, []):
            object_entity = RekognitionObjectEntity(
                camera[CONF_ENTITY_ID],
                session,
                session_config,
                conf,
                camera.get(CONF_NAME),
            )
            entities.append(object_entity)
        add_entities(entities)
    return None


class RekognitionObjectEntity(ImageProcessingEntity):
    """Rekognition Object Detection capabilities."""

    _service = "rekognition"

    def __init__(
        self, camera_entity, session, session_config, entity_config, name=None,
    ):
        """Initialize the Rekognition service."""
        super().__init__()
        self._objects = []
        self._labels = []

        self.session = session
        self.session_config = session_config
        self.camera = camera_entity
        self.conf_save_file_folder = entity_config.get(CONF_SAVE_FILE_FOLDER, None)
        self.conf_save_file_timestamp = entity_config.get(
            CONF_SAVE_FILE_TIMESTAMP, False
        )
        self._confidence = entity_config.get(CONF_CONFIDENCE, 0.0)
        if name:
            self._name = name
        else:
            self._name = f"Rekognition Object {split_entity_id(camera_entity)[1]}"

    @property
    def state_attributes(self):
        """Return device specific state attributes."""
        return {ATTR_OBJECTS: self._objects, ATTR_LABELS: self._labels}

    @property
    def state(self):
        """Return the state of the entity."""
        return len(self._objects)

    @property
    def confidence(self):
        """Return minimum confidence for send events."""
        return self._confidence

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self.camera

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    async def async_process_objects(self, objects, labels):
        """Send events with detected objects/labels and store data."""
        # Send events
        for target in objects:
            target_event_data = target.copy()
            target_event_data[ATTR_ENTITY_ID] = self.entity_id
            self.hass.bus.fire(EVENT_OBJECT_DETECTED, target_event_data)
        for label in labels:
            label_event_data = label.copy()
            label_event_data[ATTR_ENTITY_ID] = self.entity_id
            self.hass.bus.fire(EVENT_LABEL_DETECTED, label_event_data)
        # Update entity store
        self._objects = objects
        self._labels = labels

    async def compute_objects(self, client, image):
        """Detect labels in image and parse response."""
        detect_labels = await client.detect_labels(Image={"Bytes": image})
        objects, labels = get_objects(detect_labels, self.confidence)
        return objects, labels

    async def async_process_image(self, image):
        """Process image.

        This method is a coroutine.
        """
        async with self.session.create_client(
            self._service, **self.session_config
        ) as client:
            objects, labels = await self.compute_objects(client, image)
            if len(objects) > 0 and self.conf_save_file_folder:
                save_image(
                    self,
                    image,
                    self.name,
                    objects,
                    self.conf_save_file_folder,
                    self.conf_save_file_timestamp,
                )
            await self.async_process_objects(objects, labels)


class RekognitionFaceEntity(ImageProcessingFaceEntity):
    """Rekognition Face Detection/Identification capabilities."""

    _service = "rekognition"

    def __init__(
        self, camera_entity, session, session_config, entity_config, name=None,
    ):
        """Initialize the Rekognition service."""
        super().__init__()
        self.session = session
        self.session_config = session_config
        self.camera = camera_entity
        self.collection_id = entity_config[CONF_COLLECTION_ID]
        self.identify_faces = entity_config.get(CONF_IDENTIFY_FACES, False)
        self.conf_save_file_folder = entity_config.get(CONF_SAVE_FILE_FOLDER, None)
        self.conf_save_file_timestamp = entity_config.get(
            CONF_SAVE_FILE_TIMESTAMP, False
        )
        self._confidence = entity_config.get(CONF_CONFIDENCE, 0.0)
        self.detection_attributes = entity_config.get(
            CONF_DETECTION_ATTRIBUTES, "DEFAULT"
        )
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
        return self.camera

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    async def compute_faces(self, client, image):
        """Detect faces in image and parse response."""
        index_faces = await client.index_faces(
            CollectionId=self.collection_id,
            Image={"Bytes": image},
            ExternalImageId=self.camera,
            DetectionAttributes=[self.detection_attributes],
        )
        known_faces = []
        detected_faces = index_faces.get("FaceRecords", [])
        for face_record in detected_faces:
            known_face = {}
            box = compute_box(face_record["Face"]["BoundingBox"], 3)
            known_face[ATTR_NAME] = "Unknown"
            known_face[ATTR_CONFIDENCE] = face_record["Face"]["Confidence"]
            known_face["bounding_box"] = box["bounding_box"]
            known_face["centroid"] = box["centroid"]
            face_id = face_record["Face"]["FaceId"]
            # Add extra attributes
            if self.detection_attributes == "ALL":
                face_detail = face_record["FaceDetail"]
                age_range = face_detail["AgeRange"]
                known_face[ATTR_GENDER] = face_detail["Gender"]["Value"]
                known_face[ATTR_MOTION] = face_detail["Emotions"][0]["Type"]
                known_face[ATTR_GLASSES] = face_detail["Eyeglasses"]["Value"]
                known_face[ATTR_AGE] = (
                    float(age_range["High"]) + float(age_range["Low"])
                ) / 2
            # Run identification against existing collection
            if self.identify_faces:
                search_faces = await client.search_faces(
                    CollectionId=self.collection_id,
                    FaceId=face_id,
                    FaceMatchThreshold=self.confidence,
                    MaxFaces=1,
                )
                for face_match in search_faces["FaceMatches"]:
                    image_id = face_match["Face"]["ExternalImageId"]
                    # Don't accidentally match against comparison images
                    if image_id == self.camera:
                        continue
                    known_face[ATTR_NAME] = image_id
                    known_face[ATTR_CONFIDENCE] = face_match["Face"]["Confidence"]
            known_faces.append(known_face)
        return known_faces

    async def async_process_image(self, image):
        """Process image.

        This method is a coroutine.
        """
        async with self.session.create_client(
            self._service, **self.session_config
        ) as client:
            known_faces = await self.compute_faces(client, image)
            if len(known_faces) > 0 and self.conf_save_file_folder:
                save_image(
                    self,
                    image,
                    self.name,
                    known_faces,
                    self.conf_save_file_folder,
                    self.conf_save_file_timestamp,
                )
            self.async_process_faces(known_faces, len(known_faces))
