"""Volvo services."""

import logging
from typing import Any, cast
from urllib import parse

from httpx import AsyncClient, HTTPStatusError, RequestError
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers.httpx_client import create_async_httpx_client

from .const import DOMAIN
from .coordinator import VolvoConfigEntry

_LOGGER = logging.getLogger(__name__)

SERVICE_GET_IMAGE_URL = "get_image_url"
SERVICE_PARAM_ENTRY = "entry"
SERVICE_PARAM_IMAGES = "images"
SERVICE_REFRESH_SCHEMA = vol.Schema(
    {
        vol.Optional(SERVICE_PARAM_ENTRY): str,
        vol.Optional(SERVICE_PARAM_IMAGES): list[str],
    }
)

_HEADERS = {
    "Accept-Language": "en-GB",
    "Sec-Fetch-User": "?1",
}

_PARAM_IMAGE_ANGLE_MAP = {
    "exterior_back": "6",
    "exterior_back_left": "5",
    "exterior_back_right": "2",
    "exterior_front": "3",
    "exterior_front_left": "4",
    "exterior_front_right": "0",
    "exterior_side_left": "7",
    "exterior_side_right": "1",
}
_IMAGE_ANGLE_MAP = {
    "1": "right",
    "3": "front",
    "4": "threeQuartersFrontLeft",
    "5": "threeQuartersRearLeft",
    "6": "rear",
    "7": "left",
}


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_IMAGE_URL,
        _get_image_url,
        schema=SERVICE_REFRESH_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


async def _get_image_url(call: ServiceCall) -> dict[str, Any]:
    entry_id = call.data.get(SERVICE_PARAM_ENTRY, "")
    requested_images = call.data.get(SERVICE_PARAM_IMAGES)

    requested_images = (
        list(set(requested_images))
        if requested_images
        else [*_PARAM_IMAGE_ANGLE_MAP.keys(), "interior"]
    )

    client = create_async_httpx_client(call.hass)
    client.headers.update(_HEADERS)

    entry = call.hass.config_entries.async_get_entry(entry_id)
    images: dict[str, Any] = {"images": []}

    if entry and (entry := cast(VolvoConfigEntry, entry)):
        for image_type in requested_images:
            if image_type == "interior":
                images["images"].append(
                    {
                        "type": "interior",
                        "url": entry.runtime_data.context.vehicle.images.internal_image_url,
                    }
                )
            else:
                url = _parse_exterior_image_url(
                    entry.runtime_data.context.vehicle.images.exterior_image_url,
                    _PARAM_IMAGE_ANGLE_MAP[image_type],
                )

                if await _async_image_exists(client, url):
                    images["images"].append(
                        {
                            "type": image_type,
                            "url": url,
                        }
                    )

    return images


def _parse_exterior_image_url(exterior_url: str, angle: str) -> str:
    if not exterior_url:
        return ""

    url_parts = parse.urlparse(exterior_url)

    if url_parts.netloc.startswith("wizz"):
        if new_angle := _IMAGE_ANGLE_MAP.get(angle):
            current_angle = url_parts.path.split("/")[-2]
            return exterior_url.replace(current_angle, new_angle)

        return ""

    query = parse.parse_qs(url_parts.query, keep_blank_values=True)
    query["angle"] = [angle]

    return url_parts._replace(query=parse.urlencode(query, doseq=True)).geturl()


async def _async_image_exists(client: AsyncClient, url: str) -> bool:
    if not url:
        return False

    try:
        response = await client.get(url, timeout=10, follow_redirects=True)
        response.raise_for_status()
    except (RequestError, HTTPStatusError):
        _LOGGER.debug("Image does not exist: %s", url)
        return False
    else:
        return True
