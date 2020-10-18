"""Module for ColorThief (RGB extraction from images) component."""
import io
import logging

from PIL import UnidentifiedImageError
from colorthief import ColorThief
import requests

from homeassistant.components.colorthief.const import (
    ATTR_FILE_PATH,
    ATTR_LIGHT,
    ATTR_URL,
    DOMAIN,
    SERVICE_PREDOMINANT_COLOR_FILE,
    SERVICE_PREDOMINANT_COLOR_URL,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS_PCT,
    ATTR_RGB_COLOR,
    ATTR_WHITE_VALUE,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID

_LOGGER = logging.getLogger(__name__)


def setup(hass, hass_config):
    """Set up services for ColorThief integration."""

    _LOGGER.debug("Setting up ColorThief component")

    def _get_color(file_handler) -> tuple:
        """Given an image file, extract the predominant color from it."""
        try:
            cf = ColorThief(file_handler)
        except UnidentifiedImageError:
            _LOGGER.error("Bad image file provided, are you sure it's an image?")
            return

        # get_color returns a SINGLE RGB value for the given image
        color = cf.get_color(quality=1)

        _LOGGER.debug("Extracted color %s from image", color)

        return color

    def _set_light(light_entity_id, color):
        """Set the given light to our extracted RGB value."""
        service_data = {
            ATTR_ENTITY_ID: light_entity_id,
            ATTR_RGB_COLOR: color,
            ATTR_WHITE_VALUE: 255,
            ATTR_BRIGHTNESS_PCT: 100,  # TODO: Move to config option
            # ATTR_TRANSITION: 0,  # TODO: Move to config option
            # ATTR_EFFECT: "none",
        }

        _LOGGER.debug("Setting RGB %s on light %s", color, light_entity_id)

        hass.services.call(LIGHT_DOMAIN, SERVICE_TURN_ON, service_data, blocking=True)

    def predominant_color_url_service(service_call):
        """Handle call for URL based image."""
        service_data = service_call.data

        url = service_data.get(ATTR_URL)
        light_entity_id = service_data.get(ATTR_LIGHT)

        _LOGGER.debug("Getting predominant RGB from image URL '%s'", url)

        try:
            req = requests.get(url)
            req.raise_for_status()
        except requests.HTTPError as err:
            _LOGGER.error("Failed to get ColorThief image due to HTTPError: %s", err)
            return

        f = io.BytesIO(req.content)
        f.name = "colorthief.jpg"
        f.seek(0)

        color = _get_color(f)

        if color:
            _set_light(light_entity_id, color)

    hass.services.register(
        DOMAIN,
        SERVICE_PREDOMINANT_COLOR_URL,
        predominant_color_url_service,
    )

    def predominant_color_file_service(service_call):
        """Handle call for local file based image."""
        service_data = service_call.data

        file_path = service_data.get(ATTR_FILE_PATH)
        light_entity_id = service_data.get(ATTR_LIGHT)

        _LOGGER.debug("Getting predominant RGB from file path '%s'", file_path)

        color = _get_color(file_path)

        if color:
            _set_light(light_entity_id, color)

    hass.services.register(
        DOMAIN,
        SERVICE_PREDOMINANT_COLOR_FILE,
        predominant_color_file_service,
    )

    return True
