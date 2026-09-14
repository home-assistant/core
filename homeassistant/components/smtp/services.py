"""Service registration for SMTP integration."""

import probatio

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.selector import MediaSelector

from .const import (
    ATTR_ATTACHMENTS,
    ATTR_CONTENT_ID,
    ATTR_FILENAME,
    ATTR_HTML,
    ATTR_MEDIA_SOURCE,
    ATTR_PRIORITY,
    DOMAIN,
)

SERVICE_SEND_MESSAGE_SCHEMA = cv.make_entity_service_schema(
    {
        probatio.Optional(ATTR_TITLE): cv.string,
        probatio.Required(ATTR_MESSAGE): cv.string,
        probatio.Optional(ATTR_HTML): cv.string,
        probatio.Optional(ATTR_ATTACHMENTS): probatio.All(
            cv.ensure_list,
            [
                probatio.Schema(
                    {
                        probatio.Required(ATTR_MEDIA_SOURCE): MediaSelector(
                            {"accept": ["*"]}
                        ),
                        probatio.Optional(ATTR_FILENAME): cv.string,
                        probatio.Optional(ATTR_CONTENT_ID): cv.string,
                    }
                )
            ],
        ),
        probatio.Optional(ATTR_PRIORITY): probatio.In(
            ["highest", "high", "normal", "low", "lowest"]
        ),
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for SMTP integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        entity_domain=NOTIFY_DOMAIN,
        schema=SERVICE_SEND_MESSAGE_SCHEMA,
        func="smtp_send_message",
    )
