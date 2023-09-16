"""Module for color_extractor (RGB extraction from images) component."""
import asyncio
import io
import logging

import aiohttp
from colorthief import ColorThief
from PIL import UnidentifiedImageError
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    LIGHT_TURN_ON_SCHEMA,
)
from homeassistant.const import SERVICE_TURN_ON as LIGHT_SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import ATTR_PATH, ATTR_URL, DOMAIN, SERVICE_TURN_ON

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

# Extend the existing light.turn_on service schema
SERVICE_SCHEMA = vol.All(
    cv.has_at_least_one_key(ATTR_URL, ATTR_PATH),
    cv.make_entity_service_schema(
        {
            **LIGHT_TURN_ON_SCHEMA,
            vol.Exclusive(ATTR_PATH, "color_extractor"): cv.isfile,
            vol.Exclusive(ATTR_URL, "color_extractor"): cv.url,
        }
    ),
)


def _get_file(file_path):
    """Get a PIL acceptable input file reference.

    Allows us to mock patch during testing to make BytesIO stream.
    """
    return file_path


def _get_color(file_handler) -> tuple:
    """Given an image file, extract the predominant color from it."""
    color_thief = ColorThief(file_handler)

    # get_color returns a SINGLE RGB value for the given image
    color = color_thief.get_color(quality=1)

    _LOGGER.debug("Extracted RGB color %s from image", color)

    return color


async def async_setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Set up services for color_extractor integration."""

    async def async_handle_service(service_call: ServiceCall) -> None:
        """Decide which color_extractor method to call based on service."""
        service_data = dict(service_call.data)

        try:
            if ATTR_URL in service_data:
                image_type = "URL"
                image_reference = service_data.pop(ATTR_URL)
                color = await async_extract_color_from_url(image_reference)

            elif ATTR_PATH in service_data:
                image_type = "file path"
                image_reference = service_data.pop(ATTR_PATH)
                color = await hass.async_add_executor_job(
                    extract_color_from_path, image_reference
                )

        except UnidentifiedImageError as ex:
            _LOGGER.error(
                "Bad image from %s '%s' provided, are you sure it's an image? %s",
                image_type,
                image_reference,
                ex,
            )
            return

        if color:
            service_data[ATTR_RGB_COLOR] = color

            await hass.services.async_call(
                LIGHT_DOMAIN, LIGHT_SERVICE_TURN_ON, service_data, blocking=True
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TURN_ON,
        async_handle_service,
        schema=SERVICE_SCHEMA,
    )

    async def async_extract_color_from_url(url):
        """Handle call for URL based image."""
        if not hass.config.is_allowed_external_url(url):
            _LOGGER.error(
                (
                    "External URL '%s' is not allowed, please add to"
                    " 'allowlist_external_urls'"
                ),
                url,
            )
            return None

        _LOGGER.debug("Getting predominant RGB from image URL '%s'", url)

        # Download the image into a buffer for ColorThief to check against
        try:
            session = aiohttp_client.async_get_clientsession(hass)

            async with asyncio.timeout(10):
                response = await session.get(url)

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Failed to get ColorThief image due to HTTPError: %s", err)
            return None

        content = await response.content.read()

        with io.BytesIO(content) as _file:
            _file.name = "color_extractor.jpg"
            _file.seek(0)

            return _get_color(_file)

    def extract_color_from_path(file_path):
        """Handle call for local file based image."""
        if not hass.config.is_allowed_path(file_path):
            _LOGGER.error(
                (
                    "File path '%s' is not allowed, please add to"
                    " 'allowlist_external_dirs'"
                ),
                file_path,
            )
            return None

        _LOGGER.debug("Getting predominant RGB from file path '%s'", file_path)

        _file = _get_file(file_path)
        return _get_color(_file)

    return True
