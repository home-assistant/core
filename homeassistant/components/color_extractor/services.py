"""Module for color_extractor (RGB extraction from images) component."""

import asyncio
from http import HTTPStatus
import io
import logging
from typing import Any

import aiohttp
from colorthief import ColorThief
from PIL import Image, UnidentifiedImageError
import probatio

from homeassistant.components.light import (
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    LIGHT_TURN_ON_SCHEMA,
)
from homeassistant.const import SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import (
    ATTR_MIN_BRIGHTNESS,
    ATTR_PATH,
    ATTR_URL,
    DOMAIN,
    SERVICE_GET_COLOR,
)

_LOGGER = logging.getLogger(__name__)

MIN_BRIGHTNESS_SCHEMA = probatio.All(
    probatio.Coerce(int), probatio.Range(min=0, max=100)
)

# Extend the existing light.turn_on service schema
TURN_ON_SERVICE_SCHEMA = probatio.All(
    probatio.AtLeastOne(ATTR_URL, ATTR_PATH),
    cv.make_entity_service_schema(
        {
            **LIGHT_TURN_ON_SCHEMA,
            probatio.Exclusive(ATTR_PATH, "color_extractor"): cv.isfile,
            probatio.Exclusive(ATTR_URL, "color_extractor"): cv.url,
            probatio.Optional(ATTR_MIN_BRIGHTNESS): MIN_BRIGHTNESS_SCHEMA,
        }
    ),
)

GET_COLOR_SERVICE_SCHEMA = probatio.All(
    probatio.AtLeastOne(ATTR_URL, ATTR_PATH),
    {
        probatio.Exclusive(ATTR_PATH, "color_extractor"): cv.isfile,
        probatio.Exclusive(ATTR_URL, "color_extractor"): cv.url,
        probatio.Optional(ATTR_MIN_BRIGHTNESS): MIN_BRIGHTNESS_SCHEMA,
    },
)


def _get_file(file_path: str) -> str:
    """Get a PIL acceptable input file reference.

    Allows us to mock patch during testing to make BytesIO stream.
    """
    return file_path


def _get_color(file_handler: io.BytesIO | str) -> tuple[int, int, int]:
    """Given an image file, extract the predominant color from it."""
    color_thief = ColorThief(file_handler)

    # get_color returns a SINGLE RGB value for the given image
    color = color_thief.get_color(quality=1)

    _LOGGER.debug("Extracted RGB color %s from image", color)

    return color


def _get_bright_color(
    file_handler: io.BytesIO | str, min_brightness: int
) -> tuple[int, int, int] | None:
    """Extract the dominant color after excluding dark pixels."""
    with Image.open(file_handler) as image:
        image.thumbnail((256, 256))
        image = image.convert("RGBA")

        threshold = min_brightness * 255 / 100
        pixels = [
            (red, green, blue, alpha if max(red, green, blue) >= threshold else 0)
            for red, green, blue, alpha in image.getdata()
        ]
        qualifying_pixels = [
            (red, green, blue)
            for red, green, blue, alpha in pixels
            if alpha >= 125
        ]
        if not qualifying_pixels:
            return None

        # ColorThief ignores near-white pixels, so handle them directly
        # when every qualifying pixel would otherwise be discarded.
        if all(min(red, green, blue) > 250 for red, green, blue in qualifying_pixels):
            return tuple(
                round(sum(pixel[channel] for pixel in qualifying_pixels) / len(qualifying_pixels))
                for channel in range(3)
            )

        image.putdata(pixels)
        with io.BytesIO() as image_buffer:
            image.save(image_buffer, format="PNG")
            image_buffer.seek(0)
            return _get_color(image_buffer)


def _extract_color(
    file_handler: io.BytesIO | str, min_brightness: int | None
) -> tuple[int, int, int] | None:
    """Extract the predominant color with optional dark-pixel filtering."""
    if min_brightness is None:
        return _get_color(file_handler)
    return _get_bright_color(file_handler, min_brightness)


async def _async_extract_color_from_url(
    hass: HomeAssistant, url: str, min_brightness: int | None = None
) -> tuple[int, int, int] | None:
    """Handle call for URL based image."""
    if not hass.config.is_allowed_external_url(url):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="url_not_allowed",
            translation_placeholders={"url": url},
        )

    _LOGGER.debug("Getting predominant RGB from image URL '%s'", url)

    # Download the image into a buffer for ColorThief to check against
    try:
        session = aiohttp_client.async_get_clientsession(hass)

        async with asyncio.timeout(10), session.get(url) as response:
            if response.status != HTTPStatus.OK:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="http_error",
                    translation_placeholders={
                        "url": url,
                        "status": str(response.status),
                    },
                )
            content = await response.read()

    except TimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout",
            translation_placeholders={"url": url},
        ) from err
    except aiohttp.ClientError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="fetch_failed",
            translation_placeholders={"url": url, "error": str(err)},
        ) from err

    with io.BytesIO(content) as _file:
        _file.name = "color_extractor.jpg"
        _file.seek(0)

        return await hass.async_add_executor_job(_extract_color, _file, min_brightness)


def _extract_color_from_path(
    hass: HomeAssistant, file_path: str, min_brightness: int | None = None
) -> tuple[int, int, int] | None:
    """Handle call for local file based image."""
    if not hass.config.is_allowed_path(file_path):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="path_not_allowed",
            translation_placeholders={"file_path": file_path},
        )

    _LOGGER.debug("Getting predominant RGB from file path '%s'", file_path)

    _file = _get_file(file_path)
    return _extract_color(_file, min_brightness)


async def async_handle_service(service_call: ServiceCall) -> None:
    """Decide which color_extractor method to call based on service."""
    service_data = dict(service_call.data)
    min_brightness = service_data.pop(ATTR_MIN_BRIGHTNESS, None)

    try:
        if ATTR_URL in service_data:
            image_type = "URL"
            image_reference = service_data.pop(ATTR_URL)
            color = await _async_extract_color_from_url(
                service_call.hass, image_reference, min_brightness
            )

        elif ATTR_PATH in service_data:
            image_type = "file path"
            image_reference = service_data.pop(ATTR_PATH)
            color = await service_call.hass.async_add_executor_job(
                _extract_color_from_path,
                service_call.hass,
                image_reference,
                min_brightness,
            )

    except UnidentifiedImageError as ex:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_image",
            translation_placeholders={
                "image_type": image_type,
                "image_reference": image_reference,
            },
        ) from ex

    if color is None:
        _LOGGER.debug("No color meets the minimum brightness; leaving lights unchanged")
        return

    service_data[ATTR_RGB_COLOR] = color

    await service_call.hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, service_data, blocking=True
    )


async def async_handle_get_color(
    service_call: ServiceCall,
) -> dict[str, Any]:
    """Handle get_color service call."""
    service_data = dict(service_call.data)
    min_brightness = service_data.pop(ATTR_MIN_BRIGHTNESS, None)

    try:
        if ATTR_URL in service_data:
            image_type = "URL"
            image_reference = service_data.pop(ATTR_URL)
            color = await _async_extract_color_from_url(
                service_call.hass, image_reference, min_brightness
            )

        elif ATTR_PATH in service_data:
            image_type = "file path"
            image_reference = service_data.pop(ATTR_PATH)
            color = await service_call.hass.async_add_executor_job(
                _extract_color_from_path,
                service_call.hass,
                image_reference,
                min_brightness,
            )

    except UnidentifiedImageError as ex:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_image",
            translation_placeholders={
                "image_type": image_type,
                "image_reference": image_reference,
            },
        ) from ex

    return {"color": color}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the services."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_TURN_ON,
        async_handle_service,
        schema=TURN_ON_SERVICE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_COLOR,
        async_handle_get_color,
        schema=GET_COLOR_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
