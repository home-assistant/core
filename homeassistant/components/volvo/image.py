"""Volvo images."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from urllib import parse

from httpx import AsyncClient, HTTPStatusError, RequestError
from volvocarsapi.models import VolvoCarsVehicle

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.httpx_client import create_async_httpx_client

from .coordinator import VolvoConfigEntry
from .entity import VolvoBaseEntity, VolvoEntityDescription

_LOGGER = logging.getLogger(__name__)
_HEADERS = {
    "Accept-Language": "en-GB",
    "Sec-Fetch-User": "?1",
}
_IMAGE_ANGLE_MAP = {
    "1": "right",
    "3": "front",
    "4": "threeQuartersFrontLeft",
    "5": "threeQuartersRearLeft",
    "6": "rear",
    "7": "left",
}

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VolvoImageDescription(VolvoEntityDescription, ImageEntityDescription):
    """Describes a Volvo image entity."""

    image_url_fn: Callable[[VolvoCarsVehicle], str]


def _exterior_image_url(exterior_url: str, angle: str) -> str:
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


_DESCRIPTIONS: tuple[VolvoImageDescription, ...] = (
    VolvoImageDescription(
        key="exterior_back",
        image_url_fn=lambda vehicle: _exterior_image_url(
            vehicle.images.exterior_image_url, "6"
        ),
    ),
    VolvoImageDescription(
        key="exterior_back_left",
        image_url_fn=lambda vehicle: _exterior_image_url(
            vehicle.images.exterior_image_url, "5"
        ),
    ),
    VolvoImageDescription(
        key="exterior_back_right",
        image_url_fn=lambda vehicle: _exterior_image_url(
            vehicle.images.exterior_image_url, "2"
        ),
    ),
    VolvoImageDescription(
        key="exterior_front",
        image_url_fn=lambda vehicle: _exterior_image_url(
            vehicle.images.exterior_image_url, "3"
        ),
    ),
    VolvoImageDescription(
        key="exterior_front_left",
        image_url_fn=lambda vehicle: _exterior_image_url(
            vehicle.images.exterior_image_url, "4"
        ),
    ),
    VolvoImageDescription(
        key="exterior_front_right",
        image_url_fn=lambda vehicle: _exterior_image_url(
            vehicle.images.exterior_image_url, "0"
        ),
    ),
    VolvoImageDescription(
        key="exterior_side_left",
        image_url_fn=lambda vehicle: _exterior_image_url(
            vehicle.images.exterior_image_url, "7"
        ),
    ),
    VolvoImageDescription(
        key="exterior_side_right",
        image_url_fn=lambda vehicle: _exterior_image_url(
            vehicle.images.exterior_image_url, "1"
        ),
    ),
    VolvoImageDescription(
        key="interior",
        image_url_fn=lambda vehicle: vehicle.images.internal_image_url,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VolvoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up images."""
    client = create_async_httpx_client(hass)
    client.headers.update(_HEADERS)

    async_add_entities(
        [
            VolvoImage(hass, entry, description, client)
            for description in _DESCRIPTIONS
            if (
                await _async_image_exists(
                    client, description.image_url_fn(entry.runtime_data.context.vehicle)
                )
            )
            is True
        ]
    )


class VolvoImage(VolvoBaseEntity, ImageEntity):
    """Volvo image."""

    entity_description: VolvoImageDescription

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VolvoConfigEntry,
        description: VolvoImageDescription,
        client: AsyncClient,
    ) -> None:
        """Initialize."""
        VolvoBaseEntity.__init__(self, entry, description)
        ImageEntity.__init__(self, hass)

        # We need to use the client with custom headers
        self._client = client

        self._attr_image_url = self.entity_description.image_url_fn(
            entry.runtime_data.context.vehicle
        )
        self._attr_image_last_updated = datetime.now()
