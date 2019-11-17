"""Person detection using Sighthound cloud service."""
from datetime import timedelta
import logging

import simplehound.core as hound
import voluptuous as vol

from homeassistant.components.image_processing import (
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_SOURCE,
    PLATFORM_SCHEMA,
    ImageProcessingEntity,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_API_KEY
from homeassistant.core import split_entity_id
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

EVENT_PERSON_DETECTED = "image_processing.person_detected"

ATTR_BOUNDING_BOX = "bounding_box"
ATTR_PEOPLE = "people"
CONF_ACCOUNT_TYPE = "account_type"
DEV = "dev"
PROD = "prod"

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

SCAN_INTERVAL = timedelta(days=365)  # NEVER SCAN.

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_ACCOUNT_TYPE, default=DEV): vol.In([DEV, PROD]),
    }
)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the platform."""

    entities = []
    for camera in config[CONF_SOURCE]:
        sighthound = SighthoundEntity(
            config.get(CONF_API_KEY),
            config.get(CONF_ACCOUNT_TYPE),
            camera.get(CONF_ENTITY_ID),
            camera.get(CONF_NAME),
        )
        entities.append(sighthound)
    add_devices(entities)


class SighthoundEntity(ImageProcessingEntity):
    """Create a sighthound entity."""

    def __init__(self, api_key, account_type, camera_entity, name):
        """Init."""
        super().__init__()
        self._api = hound.cloud(api_key, account_type)
        self._camera = camera_entity
        if name:
            self._name = name
        else:
            self._camera_name = split_entity_id(camera_entity)[1]
            self._name = f"sighthound_{self._camera_name}"
        self._state = None
        self._image_width = None
        self._image_height = None

    def process_image(self, image):
        """Process an image."""
        detections = self._api.detect(image)
        people = hound.get_people(detections)
        self._state = len(people)

        metadata = hound.get_metadata(detections)
        self._image_width = metadata["image_width"]
        self._image_height = metadata["image_height"]
        for person in people:
            self.fire_person_detected_event(person)

    def fire_person_detected_event(self, person):
        """Send event with detected total_persons."""
        self.hass.bus.fire(
            EVENT_PERSON_DETECTED,
            {
                ATTR_ENTITY_ID: self.entity_id,
                ATTR_BOUNDING_BOX: hound.bbox_to_tf_style(
                    person["boundingBox"], self._image_width, self._image_height
                ),
            },
        )

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ATTR_PEOPLE
