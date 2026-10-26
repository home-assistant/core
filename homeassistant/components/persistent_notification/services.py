"""Services for the Persistent Notification integration."""

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import ATTR_MESSAGE, ATTR_NOTIFICATION_ID, ATTR_TITLE, DOMAIN
from .helpers import async_create, async_dismiss, async_dismiss_all

SCHEMA_SERVICE_NOTIFICATION = probatio.Schema(
    {probatio.Required(ATTR_NOTIFICATION_ID): cv.string}
)


@callback
def _create_service(call: ServiceCall) -> None:
    """Handle a create notification service call."""
    hass = call.hass
    async_create(
        hass,
        call.data[ATTR_MESSAGE],
        call.data.get(ATTR_TITLE),
        call.data.get(ATTR_NOTIFICATION_ID),
    )


@callback
def _dismiss_service(call: ServiceCall) -> None:
    """Handle the dismiss notification service call."""
    hass = call.hass
    async_dismiss(hass, call.data[ATTR_NOTIFICATION_ID])


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
        "create",
        _create_service,
        probatio.Schema(
            {
                probatio.Required(ATTR_MESSAGE): cv.string,
                probatio.Optional(ATTR_TITLE): cv.string,
                probatio.Optional(ATTR_NOTIFICATION_ID): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN, "dismiss", _dismiss_service, SCHEMA_SERVICE_NOTIFICATION
    )

    hass.services.async_register(DOMAIN, "dismiss_all", _dismiss_all_service, None)
