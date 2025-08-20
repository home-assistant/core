"""Actions for Bring! integration."""

import logging
from typing import TYPE_CHECKING

from bring_api import (
    ActivityType,
    BringAuthException,
    BringNotificationType,
    BringRequestException,
    ReactionType,
)
import voluptuous as vol

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import (
    ATTR_ACTIVITY,
    ATTR_REACTION,
    ATTR_RECEIVER,
    DOMAIN,
    SERVICE_ACTIVITY_STREAM_REACTION,
)
from .coordinator import BringConfigEntry

_LOGGER = logging.getLogger(__name__)

SERVICE_ACTIVITY_STREAM_REACTION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_REACTION): vol.All(
            vol.Upper,
            vol.Coerce(ReactionType),
        ),
    }
)


def get_config_entry(hass: HomeAssistant, entry_id: str) -> BringConfigEntry:
    """Return config entry or raise if not found or not loaded."""
    entry = hass.config_entries.async_get_entry(entry_id)
    if TYPE_CHECKING:
        assert entry
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
        )
    return entry


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Bring! integration."""

    async def async_send_activity_stream_reaction(call: ServiceCall) -> None:
        """Send a reaction in response to recent activity of a list member."""

        if (
            not (state := hass.states.get(call.data[ATTR_ENTITY_ID]))
            or not (entity := er.async_get(hass).async_get(call.data[ATTR_ENTITY_ID]))
            or not entity.config_entry_id
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entity_not_found",
                translation_placeholders={
                    ATTR_ENTITY_ID: call.data[ATTR_ENTITY_ID],
                },
            )
        config_entry = get_config_entry(hass, entity.config_entry_id)

        coordinator = config_entry.runtime_data.data

        list_uuid = entity.unique_id.split("_")[1]

        activity = state.attributes[ATTR_EVENT_TYPE]

        reaction: ReactionType = call.data[ATTR_REACTION]

        if not activity:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="activity_not_found",
            )
        try:
            await coordinator.bring.notify(
                list_uuid,
                BringNotificationType.LIST_ACTIVITY_STREAM_REACTION,
                receiver=state.attributes[ATTR_RECEIVER],
                activity=state.attributes[ATTR_ACTIVITY],
                activity_type=ActivityType(activity.upper()),
                reaction=reaction,
            )
        except (BringRequestException, BringAuthException) as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="reaction_request_failed",
            ) from e

    hass.services.async_register(
        DOMAIN,
        SERVICE_ACTIVITY_STREAM_REACTION,
        async_send_activity_stream_reaction,
        SERVICE_ACTIVITY_STREAM_REACTION_SCHEMA,
    )
