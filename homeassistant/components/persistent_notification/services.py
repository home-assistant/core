"""Services for the Persistent Notification integration."""

from enum import StrEnum

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .helpers import async_create, async_dismiss, async_dismiss_all


class PersistentNotificationService(StrEnum):
    """Store keys for persistent notification services."""

    CREATE = "create"
    DISMISS = "dismiss"
    DISMISS_ALL = "dismiss_all"


class PersistentNotificationServiceArgument(StrEnum):
    """Store keys for persistent notification service arguments."""

    MESSAGE = "message"
    NOTIFICATION_ID = "notification_id"
    TITLE = "title"


SCHEMA_SERVICE_NOTIFICATION = probatio.Schema(
    {
        probatio.Required(
            PersistentNotificationServiceArgument.NOTIFICATION_ID
        ): cv.string
    }
)


@callback
def _create_service(call: ServiceCall) -> None:
    """Handle a create notification service call."""
    hass = call.hass
    async_create(
        hass,
        call.data[PersistentNotificationServiceArgument.MESSAGE],
        call.data.get(PersistentNotificationServiceArgument.TITLE),
        call.data.get(PersistentNotificationServiceArgument.NOTIFICATION_ID),
    )


@callback
def _dismiss_service(call: ServiceCall) -> None:
    """Handle the dismiss notification service call."""
    hass = call.hass
    async_dismiss(
        hass, call.data[PersistentNotificationServiceArgument.NOTIFICATION_ID]
    )


@callback
def _dismiss_all_service(call: ServiceCall) -> None:
    """Handle the dismiss all notification service call."""
    hass = call.hass
    async_dismiss_all(hass)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Persistent Notification integration."""

    hass.services.async_register(
        DOMAIN,
        PersistentNotificationService.CREATE,
        _create_service,
        probatio.Schema(
            {
                probatio.Required(
                    PersistentNotificationServiceArgument.MESSAGE
                ): cv.string,
                probatio.Optional(
                    PersistentNotificationServiceArgument.TITLE
                ): cv.string,
                probatio.Optional(
                    PersistentNotificationServiceArgument.NOTIFICATION_ID
                ): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        PersistentNotificationService.DISMISS,
        _dismiss_service,
        SCHEMA_SERVICE_NOTIFICATION,
    )

    hass.services.async_register(
        DOMAIN, PersistentNotificationService.DISMISS_ALL, _dismiss_all_service, None
    )
