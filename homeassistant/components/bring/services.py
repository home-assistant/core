"""Actions for Bring! integration."""

from bring_api import (
    ActivityType,
    BringAuthException,
    BringNotificationType,
    BringRequestException,
    ReactionType,
)
import voluptuous as vol

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    service,
)

from .const import DOMAIN
from .coordinator import BringConfigEntry

ATTR_ACTIVITY = "uuid"
ATTR_ITEM_NAME = "item"
ATTR_NOTIFICATION_TYPE = "message"
ATTR_REACTION = "reaction"
ATTR_RECEIVER = "publicUserUuid"

SERVICE_PUSH_NOTIFICATION = "send_message"
SERVICE_ACTIVITY_STREAM_REACTION = "send_reaction"

SERVICE_ACTIVITY_STREAM_REACTION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_REACTION): vol.All(
            vol.Upper,
            vol.Coerce(ReactionType),
        ),
    }
)


@callback
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
        config_entry: BringConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, entity.config_entry_id
        )

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

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_PUSH_NOTIFICATION,
        entity_domain=TODO_DOMAIN,
        schema={
            vol.Required(ATTR_NOTIFICATION_TYPE): vol.All(
                vol.Upper, vol.Coerce(BringNotificationType)
            ),
            vol.Optional(ATTR_ITEM_NAME): cv.string,
        },
        func="async_send_message",
    )
