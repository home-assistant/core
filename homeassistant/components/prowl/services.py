"""Service registration for Prowl integration."""

from enum import StrEnum

import probatio

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN, PRIORITY_MAP


class ProwlService(StrEnum):
    """Store keys for Prowl services."""

    SEND_MESSAGE = "send_message"


class ProwlServiceArgument(StrEnum):
    """Store keys for Prowl service arguments."""

    MESSAGE = "message"
    PRIORITY = "priority"
    TITLE = "title"
    URL = "url"


SERVICE_SEND_MESSAGE_SCHEMA = cv.make_entity_service_schema(
    {
        probatio.Optional(ProwlServiceArgument.TITLE): cv.string,
        probatio.Required(ProwlServiceArgument.MESSAGE): cv.string,
        probatio.Optional(ProwlServiceArgument.PRIORITY, default="normal"): probatio.In(
            list(PRIORITY_MAP)
        ),
        # Any URL Prowl accepts, including app schemes, like the legacy action
        probatio.Optional(ProwlServiceArgument.URL): probatio.All(
            cv.string, probatio.Length(max=512)
        ),
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Prowl integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        ProwlService.SEND_MESSAGE,
        entity_domain=NOTIFY_DOMAIN,
        schema=SERVICE_SEND_MESSAGE_SCHEMA,
        func="prowl_send_message",
    )
