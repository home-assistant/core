"""Support for displaying persistent notifications."""

from collections.abc import Mapping
from functools import partial
import logging
from typing import Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType

from .const import (  # noqa: F401
    ATTR_CREATED_AT,
    ATTR_MESSAGE,
    ATTR_NOTIFICATION_ID,
    ATTR_STATUS,
    ATTR_TITLE,
    DOMAIN,
    SIGNAL_PERSISTENT_NOTIFICATIONS_UPDATED,
    Notification,
    UpdateType,
)
from .helpers import (  # noqa: F401
    _async_get_or_create_notifications,
    async_create,
    async_dismiss,
    async_dismiss_all,
    async_register_callback,
    create,
    dismiss,
)

SCHEMA_SERVICE_NOTIFICATION = probatio.Schema(
    {probatio.Required(ATTR_NOTIFICATION_ID): cv.string}
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the persistent notification component."""

    @callback
    def create_service(call: ServiceCall) -> None:
        """Handle a create notification service call."""
        async_create(
            hass,
            call.data[ATTR_MESSAGE],
            call.data.get(ATTR_TITLE),
            call.data.get(ATTR_NOTIFICATION_ID),
        )

    @callback
    def dismiss_service(call: ServiceCall) -> None:
        """Handle the dismiss notification service call."""
        async_dismiss(hass, call.data[ATTR_NOTIFICATION_ID])

    @callback
    def dismiss_all_service(call: ServiceCall) -> None:
        """Handle the dismiss all notification service call."""
        async_dismiss_all(hass)

    hass.services.async_register(
        DOMAIN,
        "create",
        create_service,
        probatio.Schema(
            {
                probatio.Required(ATTR_MESSAGE): cv.string,
                probatio.Optional(ATTR_TITLE): cv.string,
                probatio.Optional(ATTR_NOTIFICATION_ID): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN, "dismiss", dismiss_service, SCHEMA_SERVICE_NOTIFICATION
    )

    hass.services.async_register(DOMAIN, "dismiss_all", dismiss_all_service, None)

    websocket_api.async_register_command(hass, websocket_get_notifications)
    websocket_api.async_register_command(hass, websocket_subscribe_notifications)

    return True


@callback
@websocket_api.websocket_command(
    {probatio.Required("type"): "persistent_notification/get"}
)
def websocket_get_notifications(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Mapping[str, Any],
) -> None:
    """Return a list of persistent_notifications."""
    connection.send_message(
        websocket_api.result_message(
            msg["id"], list(_async_get_or_create_notifications(hass).values())
        )
    )


@callback
def _async_send_notification_update(
    connection: websocket_api.ActiveConnection,
    msg_id: int,
    update_type: UpdateType,
    notifications: dict[str, Notification],
) -> None:
    """Send persistent_notification update."""
    connection.send_message(
        websocket_api.event_message(
            msg_id, {"type": update_type, "notifications": notifications}
        )
    )


@callback
@websocket_api.websocket_command(
    {probatio.Required("type"): "persistent_notification/subscribe"}
)
def websocket_subscribe_notifications(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Mapping[str, Any],
) -> None:
    """Return a list of persistent_notifications."""
    notifications = _async_get_or_create_notifications(hass)
    msg_id = msg["id"]
    notify_func = partial(_async_send_notification_update, connection, msg_id)
    connection.subscriptions[msg_id] = async_dispatcher_connect(
        hass, SIGNAL_PERSISTENT_NOTIFICATIONS_UPDATED, notify_func
    )
    connection.send_result(msg_id)
    notify_func(UpdateType.CURRENT, notifications)
