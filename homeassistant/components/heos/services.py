"""Services for the HEOS integration."""

from dataclasses import dataclass
import logging
from typing import Final

from pyheos import CommandAuthenticationError, Heos, HeosError
import voluptuous as vol

from homeassistant.components.media_player import ATTR_MEDIA_VOLUME_LEVEL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    entity_platform,
    issue_registry as ir,
)
from homeassistant.helpers.typing import VolDictType, VolSchemaType

from .const import (
    ATTR_DESTINATION_POSITION,
    ATTR_PASSWORD,
    ATTR_QUEUE_IDS,
    ATTR_USERNAME,
    DOMAIN,
    SERVICE_GET_QUEUE,
    SERVICE_GROUP_VOLUME_DOWN,
    SERVICE_GROUP_VOLUME_SET,
    SERVICE_GROUP_VOLUME_UP,
    SERVICE_MOVE_QUEUE_ITEM,
    SERVICE_REMOVE_FROM_QUEUE,
    SERVICE_SIGN_IN,
    SERVICE_SIGN_OUT,
)
from .coordinator import HeosConfigEntry

_LOGGER = logging.getLogger(__name__)

HEOS_SIGN_IN_SCHEMA = vol.Schema(
    {vol.Required(ATTR_USERNAME): cv.string, vol.Required(ATTR_PASSWORD): cv.string}
)

HEOS_SIGN_OUT_SCHEMA = vol.Schema({})


def register(hass: HomeAssistant) -> None:
    """Register HEOS services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_SIGN_IN,
        _sign_in_handler,
        schema=HEOS_SIGN_IN_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SIGN_OUT,
        _sign_out_handler,
        schema=HEOS_SIGN_OUT_SCHEMA,
    )


@dataclass(frozen=True)
class EntityServiceDescription:
    """Describe an entity service."""

    name: str
    method_name: str
    schema: VolDictType | VolSchemaType | None = None
    supports_response: SupportsResponse = SupportsResponse.NONE

    def async_register(self, platform: entity_platform.EntityPlatform) -> None:
        """Register the service with the platform."""
        platform.async_register_entity_service(
            self.name,
            self.schema,
            self.method_name,
            supports_response=self.supports_response,
        )


REMOVE_FROM_QUEUE_SCHEMA: Final[VolDictType] = {
    vol.Required(ATTR_QUEUE_IDS): vol.All(
        cv.ensure_list,
        [vol.All(cv.positive_int, vol.Range(min=1))],
        vol.Unique(),
    )
}
GROUP_VOLUME_SET_SCHEMA: Final[VolDictType] = {
    vol.Required(ATTR_MEDIA_VOLUME_LEVEL): cv.small_float
}
MOVE_QEUEUE_ITEM_SCHEMA: Final[VolDictType] = {
    vol.Required(ATTR_QUEUE_IDS): vol.All(
        cv.ensure_list,
        [vol.All(vol.Coerce(int), vol.Range(min=1, max=1000))],
        vol.Unique(),
    ),
    vol.Required(ATTR_DESTINATION_POSITION): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=1000)
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


def register_media_player_services() -> None:
    """Register media_player entity services."""
    platform = entity_platform.async_get_current_platform()
    for service in MEDIA_PLAYER_ENTITY_SERVICES:
        service.async_register(platform)


def _get_controller(hass: HomeAssistant) -> Heos:
    """Get the HEOS controller instance."""
    _LOGGER.warning(
        "Actions 'heos.sign_in' and 'heos.sign_out' are deprecated and will be removed in the 2025.8.0 release"
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        "sign_in_out_deprecated",
        breaks_in_ha_version="2025.8.0",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="sign_in_out_deprecated",
    )

    entry: HeosConfigEntry | None = (
        hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, DOMAIN)
    )

    if not entry or not entry.state == ConfigEntryState.LOADED:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="integration_not_loaded"
        )
    return entry.runtime_data.heos


async def _sign_in_handler(service: ServiceCall) -> None:
    """Sign in to the HEOS account."""
    controller = _get_controller(service.hass)
    username = service.data[ATTR_USERNAME]
    password = service.data[ATTR_PASSWORD]
    try:
        await controller.sign_in(username, password)
    except CommandAuthenticationError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="sign_in_auth_error"
        ) from err
    except HeosError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="sign_in_error",
            translation_placeholders={"error": str(err)},
        ) from err


async def _sign_out_handler(service: ServiceCall) -> None:
    """Sign out of the HEOS account."""
    controller = _get_controller(service.hass)
    try:
        await controller.sign_out()
    except HeosError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="sign_out_error",
            translation_placeholders={"error": str(err)},
        ) from err
