"""Module for color_extractor (RGB extraction from images) component."""
import asyncio
import io
import logging

from PIL import UnidentifiedImageError
import aiohttp
import async_timeout
from colorthief import ColorThief
import voluptuous as vol

from homeassistant.components.color_extractor.const import (
    ATTR_PATH,
    ATTR_URL,
    DOMAIN,
    SERVICE_TURN_ON,
)
from homeassistant.components.light import (
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    LIGHT_TURN_ON_SCHEMA,
    SERVICE_TURN_ON as LIGHT_SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

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


def _get_colors(file_handler, light_count) -> tuple:
    """Given an image file, extract the predominant color from it."""
    color_thief = ColorThief(file_handler)

    if light_count == 1:
        # get_color returns a single RGB value for the given image
        colors = [color_thief.get_color(quality=1)]
        _LOGGER.debug("get_palette response: %s", colors)
    else:
        colors = color_thief.get_palette(quality=1, color_count=light_count)
        _LOGGER.debug("get_palette response: %s", colors)

    _LOGGER.debug("Extracted %d RGB colors from image", len(colors))

    return colors


async def async_setup(hass, hass_config):
    """Set up services for color_extractor integration."""

    async def async_handle_service(service_call):
        """Decide which color_extractor method to call based on service."""
        service_data = dict(service_call.data)
        number_of_lights = len(service_data[ATTR_ENTITY_ID])

        _LOGGER.debug("Number of lights: %d", number_of_lights)

        try:
            if ATTR_URL in service_data:
                image_type = "URL"
                image_reference = service_data.pop(ATTR_URL)
                colors = await async_extract_colors_from_url(
                    image_reference, number_of_lights
                )

            elif ATTR_PATH in service_data:
                image_type = "file path"
                image_reference = service_data.pop(ATTR_PATH)
                colors = await hass.async_add_executor_job(
                    extract_colors_from_path, image_reference, number_of_lights
                )

        except UnidentifiedImageError as ex:
            _LOGGER.error(
                "Bad image from %s '%s' provided, are you sure it's an image? %s",
                image_type,
                image_reference,
                ex,
            )
            return

        if colors:
            if isinstance(service_data[ATTR_ENTITY_ID], list):
                lights = service_data[ATTR_ENTITY_ID]
            else:
                lights = [service_data[ATTR_ENTITY_ID]]

            for _, (entity_id, color) in enumerate(zip(lights, colors)):
                service_data[ATTR_ENTITY_ID] = entity_id
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

    async def async_extract_colors_from_url(url, light_count):
        """Handle call for URL based image."""
        if not hass.config.is_allowed_external_url(url):
            _LOGGER.error(
                "External URL '%s' is not allowed, please add to 'allowlist_external_urls'",
                url,
            )
            return None

        _LOGGER.debug("Getting predominant RGB from image URL '%s'", url)

        # Download the image into a buffer for ColorThief to check against
        try:
            session = aiohttp_client.async_get_clientsession(hass)

            with async_timeout.timeout(10):
                response = await session.get(url)

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Failed to get ColorThief image due to HTTPError: %s", err)
            return None

        content = await response.content.read()

        with io.BytesIO(content) as _file:
            _file.name = "color_extractor.jpg"
            _file.seek(0)

            return _get_colors(_file, light_count)

    def extract_colors_from_path(file_path, light_count):
        """Handle call for local file based image."""
        if not hass.config.is_allowed_path(file_path):
            _LOGGER.error(
                "File path '%s' is not allowed, please add to 'allowlist_external_dirs'",
                file_path,
            )
            return None

        _LOGGER.debug("Getting predominant RGB from file path '%s'", file_path)

        _file = _get_file(file_path)
        return _get_colors(_file, light_count)

    return True
