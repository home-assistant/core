"""Volvo services."""

import asyncio
import logging
from typing import Any
from urllib import parse

from httpx import AsyncClient, HTTPError, HTTPStatusError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN
from .coordinator import VolvoConfigEntry

_LOGGER = logging.getLogger(__name__)

CONF_CONFIG_ENTRY_ID = "entry"
CONF_IMAGE_TYPES = "images"
SERVICE_GET_IMAGE_URL = "get_image_url"
SERVICE_GET_IMAGE_URL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONFIG_ENTRY_ID): str,
        vol.Optional(CONF_IMAGE_TYPES): vol.All(cv.ensure_list, [str]),
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
        schema=SERVICE_GET_IMAGE_URL_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


async def _get_image_url(call: ServiceCall) -> dict[str, Any]:
    entry_id = call.data.get(CONF_CONFIG_ENTRY_ID, "")
    requested_images = call.data.get(CONF_IMAGE_TYPES, [])

    entry = _async_get_config_entry(call.hass, entry_id)
    image_types = _get_requested_image_types(requested_images)
    client = get_async_client(call.hass)

    # Build (type, url) pairs for all requested image types up front
    candidates: list[tuple[str, str]] = []

    for image_type in image_types:
        if image_type == "interior":
            url = entry.runtime_data.context.vehicle.images.internal_image_url or ""
        else:
            url = _parse_exterior_image_url(
                entry.runtime_data.context.vehicle.images.exterior_image_url,
                _PARAM_IMAGE_ANGLE_MAP[image_type],
            )

        candidates.append((image_type, url))

    # Interior images exist if their URL is populated; exterior images require an HTTP check
    async def _check_exists(image_type: str, url: str) -> bool:
        if image_type == "interior":
            return bool(url)
        return await _async_image_exists(client, url)

    # Run checks in parallel
    exists_results = await asyncio.gather(
        *(_check_exists(image_type, url) for image_type, url in candidates)
    )

    return {
        "images": [
            {"type": image_type, "url": url}
            for (image_type, url), exists in zip(
                candidates, exists_results, strict=True
            )
            if exists
        ]
    }


def _async_get_config_entry(hass: HomeAssistant, entry_id: str) -> VolvoConfigEntry:
    if not entry_id:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_entry_id",
            translation_placeholders={"entry_id": entry_id},
        )

    if not (entry := hass.config_entries.async_get_entry(entry_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_found",
            translation_placeholders={"entry_id": entry_id},
        )

    if entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_entry",
            translation_placeholders={"entry_id": entry.entry_id},
        )

    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
            translation_placeholders={"entry_id": entry.entry_id},
        )

    return entry


def _get_requested_image_types(requested_image_types: list[str]) -> list[str]:
    allowed_image_types = [*_PARAM_IMAGE_ANGLE_MAP.keys(), "interior"]

    if not requested_image_types:
        return allowed_image_types

    image_types: list[str] = []

    for image_type in requested_image_types:
        if image_type in image_types:
            continue

        if image_type not in allowed_image_types:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_image_type",
                translation_placeholders={"image_type": image_type},
            )

        image_types.append(image_type)

    return image_types


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
        async with client.stream(
            "GET", url, headers=_HEADERS, timeout=10, follow_redirects=True
        ) as response:
            response.raise_for_status()
    except HTTPStatusError as ex:
        status = ex.response.status_code if ex.response is not None else None

        if status in (404, 410):
            _LOGGER.debug("Image does not exist: %s", url)
            return False

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="image_error",
            translation_placeholders={"url": url},
        ) from ex
    except HTTPError as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="image_error",
            translation_placeholders={"url": url},
        ) from ex
    else:
        return True
