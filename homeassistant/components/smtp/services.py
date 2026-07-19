"""Service registration for SMTP integration."""

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.selector import MediaSelector

from .const import (
    ATTR_ATTACHMENT,
    ATTR_ATTACHMENTS,
    ATTR_CONTENT_ID,
    ATTR_FILENAME,
    ATTR_HTML,
    DOMAIN,
)

SERVICE_SEND_MESSAGE_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Optional(ATTR_TITLE, default=ATTR_TITLE_DEFAULT): cv.string,
        vol.Optional(ATTR_MESSAGE, default=""): cv.string,
        vol.Optional(ATTR_HTML): cv.string,
        vol.Optional(ATTR_ATTACHMENTS): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(ATTR_ATTACHMENT): MediaSelector({"accept": ["*"]}),
                        vol.Optional(ATTR_FILENAME): cv.string,
                        vol.Optional(ATTR_CONTENT_ID): cv.string,
                    }
                )
            ],
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
