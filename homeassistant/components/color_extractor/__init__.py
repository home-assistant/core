"""Module for color_extractor (RGB extraction from images) component."""
import asyncio
import io
import logging

from PIL import UnidentifiedImageError
import aiohttp
import async_timeout
from colorthief import ColorThief

from homeassistant.components.color_extractor.const import (
    ATTR_FILE_PATH,
    ATTR_LIGHT_ENTITY_ID,
    ATTR_URL,
    DOMAIN,
    SERVICE_PREDOMINANT_COLOR_FILE,
    SERVICE_PREDOMINANT_COLOR_URL,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS_PCT,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import aiohttp_client

_LOGGER = logging.getLogger(__name__)


def _get_file(file_path):
    return file_path


async def async_setup(hass, hass_config):
    """Set up services for color_extractor integration."""

    _LOGGER.debug("Setting up color_extractor component")

    async def _async_get_color(file_handler) -> tuple:
        """Given an image file, extract the predominant color from it."""
        try:
            color_thief = await hass.async_add_executor_job(ColorThief, file_handler)
        except UnidentifiedImageError as ex:
            _LOGGER.error("Bad image file provided, are you sure it's an image? %s", ex)
            return

        # get_color returns a SINGLE RGB value for the given image
        color = color_thief.get_color(quality=1)

        _LOGGER.debug("Extracted RGB color %s from image", color)

        return color

    async def _async_set_light(
        light_entity_id, color, brightness_pct=None, transition=None
    ):
        """Set the given light to our extracted RGB value."""
        service_data = {
            ATTR_ENTITY_ID: light_entity_id,
            ATTR_RGB_COLOR: color,
        }

        if brightness_pct:
            service_data[ATTR_BRIGHTNESS_PCT] = brightness_pct

        if transition:
            service_data[ATTR_TRANSITION] = transition

        _LOGGER.debug("Setting RGB %s on light %s", color, light_entity_id)

        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_ON, service_data, blocking=True
        )

    async def async_predominant_color_url_service(service_call):
        """Handle call for URL based image."""
        service_data = service_call.data

        url = service_data.get(ATTR_URL)
        light_entity_id = service_data.get(ATTR_LIGHT_ENTITY_ID)

        # Optional fields
        brightness_pct = service_data.get(ATTR_BRIGHTNESS_PCT)
        transition = service_data.get(ATTR_TRANSITION)

        _LOGGER.debug("Getting predominant RGB from image URL '%s'", url)

        try:
            session = aiohttp_client.async_get_clientsession(hass)

            with async_timeout.timeout(10):
                response = await session.get(url)

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Failed to get ColorThief image due to HTTPError: %s", err)
            return

        content = await response.content.read()

        with io.BytesIO(content) as _file:
            _file.name = "colorthief.jpg"
            _file.seek(0)

            color = await _async_get_color(_file)

        if color:
            await _async_set_light(light_entity_id, color, brightness_pct, transition)

    hass.services.async_register(
        DOMAIN,
        SERVICE_PREDOMINANT_COLOR_URL,
        async_predominant_color_url_service,
    )

    async def async_predominant_color_file_service(service_call):
        """Handle call for local file based image."""
        service_data = service_call.data

        file_path = service_data.get(ATTR_FILE_PATH)
        light_entity_id = service_data.get(ATTR_LIGHT_ENTITY_ID)

        # Optional fields
        brightness_pct = service_data.get(ATTR_BRIGHTNESS_PCT)
        transition = service_data.get(ATTR_TRANSITION)

        _LOGGER.debug("Getting predominant RGB from file path '%s'", file_path)

        _file = _get_file(file_path)
        color = await _async_get_color(_file)

        if color:
            await _async_set_light(light_entity_id, color, brightness_pct, transition)

    hass.services.async_register(
        DOMAIN,
        SERVICE_PREDOMINANT_COLOR_FILE,
        async_predominant_color_file_service,
    )

    return True
