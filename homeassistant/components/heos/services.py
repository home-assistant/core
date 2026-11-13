"""Services for the HEOS integration."""

from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Final

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.helpers.typing import VolDictType, VolSchemaType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HeosService(StrEnum):
    """Store keys for HEOS services."""

    GET_QUEUE = "get_queue"
    REMOVE_FROM_QUEUE = "remove_from_queue"
    MOVE_QUEUE_ITEM = "move_queue_item"
    GROUP_VOLUME_SET = "group_volume_set"
    GROUP_VOLUME_DOWN = "group_volume_down"
    GROUP_VOLUME_UP = "group_volume_up"


class HeosServiceArgument(StrEnum):
    """Store keys for HEOS service arguments."""

    QUEUE_IDS = "queue_ids"
    DESTINATION_POSITION = "destination_position"
    VOLUME_LEVEL = "volume_level"


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
    probatio.Required(HeosServiceArgument.QUEUE_IDS): probatio.All(
        probatio.EnsureList(),
        [probatio.All(cv.positive_int, probatio.Range(min=1))],
        probatio.Unique(),
    )
}
GROUP_VOLUME_SET_SCHEMA: Final[VolDictType] = {
    probatio.Required(HeosServiceArgument.VOLUME_LEVEL): cv.small_float
}
MOVE_QEUEUE_ITEM_SCHEMA: Final[VolDictType] = {
    probatio.Required(HeosServiceArgument.QUEUE_IDS): probatio.All(
        probatio.EnsureList(),
        [probatio.All(probatio.Coerce(int), probatio.Range(min=1, max=1000))],
        probatio.Unique(),
    ),
    probatio.Required(HeosServiceArgument.DESTINATION_POSITION): probatio.All(
        probatio.Coerce(int), probatio.Range(min=1, max=1000)
    ),
}

MEDIA_PLAYER_ENTITY_SERVICES: Final = (
    # Player queue services
    EntityServiceDescription(
        HeosService.GET_QUEUE,
        "async_get_queue",
        supports_response=SupportsResponse.ONLY,
    ),
    EntityServiceDescription(
        HeosService.REMOVE_FROM_QUEUE,
        "async_remove_from_queue",
        REMOVE_FROM_QUEUE_SCHEMA,
    ),
    EntityServiceDescription(
        HeosService.MOVE_QUEUE_ITEM, "async_move_queue_item", MOVE_QEUEUE_ITEM_SCHEMA
    ),
    # Group volume services
    EntityServiceDescription(
        HeosService.GROUP_VOLUME_SET,
        "async_set_group_volume_level",
        GROUP_VOLUME_SET_SCHEMA,
    ),
    EntityServiceDescription(HeosService.GROUP_VOLUME_DOWN, "async_group_volume_down"),
    EntityServiceDescription(HeosService.GROUP_VOLUME_UP, "async_group_volume_up"),
)
