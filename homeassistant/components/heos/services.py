"""Services for the HEOS integration."""

from dataclasses import dataclass
import logging
from typing import Final

import probatio

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.helpers.typing import VolDictType, VolSchemaType

from .const import (
    ATTR_DESTINATION_POSITION,
    ATTR_QUEUE_IDS,
    DOMAIN,
    SERVICE_GET_QUEUE,
    SERVICE_GROUP_VOLUME_DOWN,
    SERVICE_GROUP_VOLUME_SET,
    SERVICE_GROUP_VOLUME_UP,
    SERVICE_MOVE_QUEUE_ITEM,
    SERVICE_REMOVE_FROM_QUEUE,
)

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register HEOS services."""
    for description in MEDIA_PLAYER_ENTITY_SERVICES:
        async_register_platform_entity_service(
            hass,
            DOMAIN,
            description.name,
            entity_domain=MEDIA_PLAYER_DOMAIN,
            schema=description.schema,
            func=description.method_name,
            supports_response=description.supports_response,
        )


@dataclass(frozen=True)
class EntityServiceDescription:
    """Describe an entity service."""

    name: str
    method_name: str
    schema: VolDictType | VolSchemaType | None = None
    supports_response: SupportsResponse = SupportsResponse.NONE


REMOVE_FROM_QUEUE_SCHEMA: Final[VolDictType] = {
    probatio.Required(ATTR_QUEUE_IDS): probatio.All(
        probatio.EnsureList(),
        [probatio.All(cv.positive_int, probatio.Range(min=1))],
        probatio.Unique(),
    )
}
GROUP_VOLUME_SET_SCHEMA: Final[VolDictType] = {
    probatio.Required(ATTR_MEDIA_VOLUME_LEVEL): cv.small_float
}
MOVE_QEUEUE_ITEM_SCHEMA: Final[VolDictType] = {
    probatio.Required(ATTR_QUEUE_IDS): probatio.All(
        probatio.EnsureList(),
        [probatio.All(probatio.Coerce(int), probatio.Range(min=1, max=1000))],
        probatio.Unique(),
    ),
    probatio.Required(ATTR_DESTINATION_POSITION): probatio.All(
        probatio.Coerce(int), probatio.Range(min=1, max=1000)
    ),
}

MEDIA_PLAYER_ENTITY_SERVICES: Final = (
    # Player queue services
    EntityServiceDescription(
        SERVICE_GET_QUEUE, "async_get_queue", supports_response=SupportsResponse.ONLY
    ),
    EntityServiceDescription(
        SERVICE_REMOVE_FROM_QUEUE, "async_remove_from_queue", REMOVE_FROM_QUEUE_SCHEMA
    ),
    EntityServiceDescription(
        SERVICE_MOVE_QUEUE_ITEM, "async_move_queue_item", MOVE_QEUEUE_ITEM_SCHEMA
    ),
    # Group volume services
    EntityServiceDescription(
        SERVICE_GROUP_VOLUME_SET,
        "async_set_group_volume_level",
        GROUP_VOLUME_SET_SCHEMA,
    ),
    EntityServiceDescription(SERVICE_GROUP_VOLUME_DOWN, "async_group_volume_down"),
    EntityServiceDescription(SERVICE_GROUP_VOLUME_UP, "async_group_volume_up"),
)
