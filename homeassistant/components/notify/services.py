"""Services for the notify integration."""

import probatio

from homeassistant.components import persistent_notification as pn
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    DATA_COMPONENT,
    DOMAIN,
    NOTIFY_SERVICE_SCHEMA,
    NotifyService,
    NotifyServiceArgument,
)


async def _async_persistent_notification(service: ServiceCall) -> None:
    """Send notification via the built-in persistent_notify integration."""
    message: str = service.data[NotifyServiceArgument.MESSAGE]
    title: str | None = service.data.get(NotifyServiceArgument.TITLE)

    notification_id = None
    if data := service.data.get(NotifyServiceArgument.DATA):
        notification_id = data.get(pn.ATTR_NOTIFICATION_ID)

    pn.async_create(service.hass, message, title, notification_id)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the notify services."""
    hass.data[DATA_COMPONENT].async_register_entity_service(
        NotifyService.SEND_MESSAGE,
        {
            probatio.Required(NotifyServiceArgument.MESSAGE): cv.string,
            probatio.Optional(NotifyServiceArgument.TITLE): cv.string,
        },
        "_async_send_message",
    )

    hass.services.async_register(
        DOMAIN,
        NotifyService.PERSISTENT_NOTIFICATION,
        _async_persistent_notification,
        schema=NOTIFY_SERVICE_SCHEMA,
    )
