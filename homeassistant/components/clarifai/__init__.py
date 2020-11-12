"""Support for the Clarifai integration."""
import logging

import voluptuous as vol

from homeassistant.components.camera import async_get_image
from homeassistant.components.image_processing import DOMAIN as IMAGE_PROCESSING
from homeassistant.const import ATTR_ENTITY_ID, CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .api import Clarifai
from .const import (
    APP_ID,
    DEFAULT,
    DOMAIN,
    EVENT_PREDICTION,
    RESULT_FORMAT,
    SERVICE_PREDICT,
    WORKFLOW_ERROR,
    WORKFLOW_ID,
)
from .image_processing import IMAGE_PROCESSING_SCHEMA

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN): cv.string,
                vol.Optional(IMAGE_PROCESSING): vol.All(
                    cv.ensure_list, [IMAGE_PROCESSING_SCHEMA]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Clarifai integration."""
    access_token = config[DOMAIN][CONF_ACCESS_TOKEN]
    clarifai = Clarifai(access_token)

    # Validate connection with Clarifai API by listing user's applications
    try:
        await hass.async_add_executor_job(clarifai.verify_access)
    except HomeAssistantError as err:
        _LOGGER.error("Could not connect to Clarifai API with error: %s", err)

    # Store Clarifai API object in hass.data for later use
    hass.data[DOMAIN] = {"api": clarifai}

    # Set up image processing platform
    if IMAGE_PROCESSING in config[DOMAIN]:
        hass.data[DOMAIN][IMAGE_PROCESSING] = config[DOMAIN][IMAGE_PROCESSING]
        hass.async_create_task(
            hass.helpers.discovery.async_load_platform(
                IMAGE_PROCESSING, DOMAIN, {}, config
            )
        )

    register_services(hass)
    return True


def register_services(hass):
    """Register services for the Clarifai integration."""
    clarifai = hass.data[DOMAIN]

    predict_service_schema = vol.Schema(
        {
            vol.Required(APP_ID): cv.string,
            vol.Required(WORKFLOW_ID): cv.string,
            vol.Required(ATTR_ENTITY_ID): cv.entity_id,
            vol.Optional(RESULT_FORMAT, default=DEFAULT): cv.string,
        }
    )

    async def async_workflow_predict_service(service):
        """Make a prediction by getting the results from a workflow."""
        app_id = service.data[APP_ID]
        workflow_id = service.data[WORKFLOW_ID]
        result_format = service.data[RESULT_FORMAT]
        camera_entity = service.data[ATTR_ENTITY_ID]

        try:
            image = await async_get_image(hass, camera_entity)
            results = await hass.async_add_executor_job(
                clarifai.post_workflow_results,
                app_id,
                workflow_id,
                result_format,
                image.content,
            )
            hass.bus.async_fire(EVENT_PREDICTION, results)
        except HomeAssistantError as err:
            _LOGGER.error(
                WORKFLOW_ERROR, workflow_id, err,
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PREDICT,
        async_workflow_predict_service,
        schema=predict_service_schema,
    )
