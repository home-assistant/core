"""Component for image processing using Clarifai workflow predictions."""
import logging

import voluptuous as vol

from homeassistant.components.image_processing import (
    CONF_ENTITY_ID,
    CONF_SOURCE,
    DOMAIN as IMAGE_PROCESSING,
    SOURCE_SCHEMA,
    ImageProcessingEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    APP_ID,
    DEFAULT,
    DOMAIN,
    EVENT_PREDICTION,
    RESULT_FORMAT,
    WORKFLOW_ERROR,
    WORKFLOW_ID,
)

_LOGGER = logging.getLogger(__name__)

IMAGE_PROCESSING_SCHEMA = vol.Schema(
    {
        vol.Required(APP_ID): cv.string,
        vol.Required(WORKFLOW_ID): cv.string,
        vol.Optional(RESULT_FORMAT, default=DEFAULT): cv.string,
        vol.Required(CONF_SOURCE): vol.All(cv.ensure_list, [SOURCE_SCHEMA]),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Clarifai image processing platform."""
    if discovery_info is None:
        return

    clarifai = hass.data[DOMAIN]["api"]

    for ip_config in hass.data[DOMAIN][IMAGE_PROCESSING]:
        app_id = ip_config[APP_ID]
        workflow_id = ip_config[WORKFLOW_ID]
        result_format = ip_config[RESULT_FORMAT]
        cameras = ip_config[CONF_SOURCE]

        # Set up an image processing entity for each camera in config
        entities = []
        for camera in cameras:
            entities.append(
                ClarifaiImageProcessingEntity(
                    camera[CONF_ENTITY_ID],
                    clarifai,
                    app_id,
                    workflow_id,
                    result_format,
                    camera.get(CONF_NAME),
                )
            )

        add_entities(entities)


class ClarifaiImageProcessingEntity(ImageProcessingEntity):
    """Component for continually processing an image on a regular interval using Clarifai workflows."""

    def __init__(
        self, camera_entity, api, app_id, workflow_id, result_format, name=None
    ):
        """Initialize Clarifai image processing entity."""
        super().__init__()

        self._camera = camera_entity
        self._api = api
        self._app_id = app_id
        self._workflow_id = workflow_id
        self._result_format = result_format
        if name:
            self._name = name
        else:
            self._name = f"{DOMAIN} {split_entity_id(camera_entity)[1]}"

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
