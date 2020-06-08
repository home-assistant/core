"""Component for image processing using Clarifai workflow predictions."""
import logging

import voluptuous as vol

from homeassistant.components.image_processing import (
    CONF_ENTITY_ID,
    CONF_SOURCE,
    PLATFORM_SCHEMA,
    ImageProcessingEntity,
)
from homeassistant.core import split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_APP_ID,
    CONF_RESULT_FORMAT,
    CONF_WORKFLOW_ID,
    DOMAIN,
    EVENT_PREDICTION,
    WORKFLOW_ERROR,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_APP_ID): cv.string,
        vol.Required(CONF_WORKFLOW_ID): cv.string,
        vol.Optional(CONF_RESULT_FORMAT): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Clarifai image processing platform."""
    clarifai = hass.data[DOMAIN]
    app_id = config[CONF_APP_ID]
    workflow_id = config[CONF_WORKFLOW_ID]
    result_format = config[CONF_RESULT_FORMAT]

    # Set up an image processing entity for each camera in config
    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(
            ClarifaiImageProcessingEntity(
                camera[CONF_ENTITY_ID], clarifai, app_id, workflow_id, result_format
            )
        )

    add_entities(entities)


class ClarifaiImageProcessingEntity(ImageProcessingEntity):
    """Component for continually processing an image on a regular interval using Clarifai workflows."""

    def __init__(self, camera_entity, api, app_id, workflow_id, result_format):
        """Initialize Clarifai image processing entity."""
        super().__init__()

        self._camera = camera_entity
        self._api = api
        self._app_id = app_id
        self._workflow_id = workflow_id
        self._result_format = result_format
        self._name = (
            f"Clarifai {workflow_id}, Camera {split_entity_id(camera_entity)[1]}"
        )

    @property
    def camera_entity(self):
        """Return camera entity."""
        return self._camera

    @property
    def name(self):
        """Return the name of the image processing entity."""
        return self._name

    def process_image(self, image):
        """Process an image using a Clarifai workflow."""
        try:
            results = self._api.post_workflow_results(
                self._app_id, self._workflow_id, self._result_format, image
            )
            self.hass.bus.fire(EVENT_PREDICTION, results)
        except HomeAssistantError as err:
            _LOGGER.error(
                WORKFLOW_ERROR, self._workflow_id, err,
            )
