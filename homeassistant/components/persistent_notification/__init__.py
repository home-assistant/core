"""Support for displaying persistent notifications."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import Context, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

ATTR_CREATED_AT = "created_at"
ATTR_MESSAGE = "message"
ATTR_NOTIFICATION_ID = "notification_id"
ATTR_TITLE = "title"
ATTR_STATUS = "status"

DOMAIN = "persistent_notification"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

EVENT_PERSISTENT_NOTIFICATIONS_UPDATED = "persistent_notifications_updated"

SCHEMA_SERVICE_NOTIFICATION = vol.Schema(
    {vol.Required(ATTR_NOTIFICATION_ID): cv.string}
)

DEFAULT_OBJECT_ID = "notification"
_LOGGER = logging.getLogger(__name__)

STATE = "notifying"
STATUS_UNREAD = "unread"
STATUS_READ = "read"


@bind_hass
def create(
    hass: HomeAssistant,
    message: str,
    title: str | None = None,
    notification_id: str | None = None,
) -> None:
    """Generate a notification."""
    hass.add_job(async_create, hass, message, title, notification_id)


@bind_hass
def dismiss(hass: HomeAssistant, notification_id: str) -> None:
    """Remove a notification."""
    hass.add_job(async_dismiss, hass, notification_id)


@callback
@bind_hass
def async_create(
    hass: HomeAssistant,
    message: str,
    title: str | None = None,
    notification_id: str | None = None,
    *,
    context: Context | None = None,
) -> None:
    """Generate a notification."""
    if (notifications := hass.data.get(DOMAIN)) is None:
        notifications = hass.data[DOMAIN] = {}

    if notification_id is not None:
        entity_id = ENTITY_ID_FORMAT.format(slugify(notification_id))
    else:
        entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, DEFAULT_OBJECT_ID, hass=hass
        )
        notification_id = entity_id.split(".")[1]

    attr: dict[str, str] = {ATTR_MESSAGE: message}
    if title is not None:
        attr[ATTR_TITLE] = title
        attr[ATTR_FRIENDLY_NAME] = title

    hass.states.async_set(entity_id, STATE, attr, context=context)

    # Store notification and fire event
    # This will eventually replace state machine storage
    notifications[entity_id] = {
        ATTR_MESSAGE: message,
        ATTR_NOTIFICATION_ID: notification_id,
        ATTR_STATUS: STATUS_UNREAD,
        ATTR_TITLE: title,
        ATTR_CREATED_AT: dt_util.utcnow(),
    }

    hass.bus.async_fire(EVENT_PERSISTENT_NOTIFICATIONS_UPDATED, context=context)


@callback
@bind_hass
def async_dismiss(
    hass: HomeAssistant, notification_id: str, *, context: Context | None = None
) -> None:
    """Remove a notification."""
    if (notifications := hass.data.get(DOMAIN)) is None:
        notifications = hass.data[DOMAIN] = {}

    entity_id = ENTITY_ID_FORMAT.format(slugify(notification_id))

    if entity_id not in notifications:
        return

    hass.states.async_remove(entity_id, context)

    del notifications[entity_id]
    hass.bus.async_fire(EVENT_PERSISTENT_NOTIFICATIONS_UPDATED)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the persistent notification component."""
    notifications = hass.data.setdefault(DOMAIN, {})

    @callback
    def create_service(call: ServiceCall) -> None:
        """Handle a create notification service call."""
        async_create(
            hass,
            call.data[ATTR_MESSAGE],
            call.data.get(ATTR_TITLE),
            call.data.get(ATTR_NOTIFICATION_ID),
            context=call.context,
        )

    @callback
    def dismiss_service(call: ServiceCall) -> None:
        """Handle the dismiss notification service call."""
        async_dismiss(hass, call.data[ATTR_NOTIFICATION_ID], context=call.context)

    @callback
    def mark_read_service(call: ServiceCall) -> None:
        """Handle the mark_read notification service call."""
        notification_id = call.data.get(ATTR_NOTIFICATION_ID)
        entity_id = ENTITY_ID_FORMAT.format(slugify(notification_id))

        if entity_id not in notifications:
            _LOGGER.error(
                "Marking persistent_notification read failed: "
                "Notification ID %s not found",
                notification_id,
            )
            return

        notifications[entity_id][ATTR_STATUS] = STATUS_READ
        hass.bus.async_fire(
            EVENT_PERSISTENT_NOTIFICATIONS_UPDATED, context=call.context
        )

    hass.services.async_register(
        DOMAIN,
        "create",
        create_service,
        vol.Schema(
            {
                vol.Required(ATTR_MESSAGE): vol.Any(cv.dynamic_template, cv.string),
                vol.Optional(ATTR_TITLE): vol.Any(cv.dynamic_template, cv.string),
                vol.Optional(ATTR_NOTIFICATION_ID): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN, "dismiss", dismiss_service, SCHEMA_SERVICE_NOTIFICATION
    )

    hass.services.async_register(
        DOMAIN, "mark_read", mark_read_service, SCHEMA_SERVICE_NOTIFICATION
    )

    websocket_api.async_register_command(hass, websocket_get_notifications)

    return True


@callback
@websocket_api.websocket_command({vol.Required("type"): "persistent_notification/get"})
def websocket_get_notifications(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Mapping[str, Any],
) -> None:
    """Return a list of persistent_notifications."""
    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            [
                {
                    key: data[key]
                    for key in (
                        ATTR_NOTIFICATION_ID,
                        ATTR_MESSAGE,
                        ATTR_STATUS,
                        ATTR_TITLE,
                        ATTR_CREATED_AT,
                    )
                }
                for data in hass.data[DOMAIN].values()
            ],
        )
    )
