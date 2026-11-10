"""Service registration for SMTP integration."""

import probatio

from homeassistant.components.notify import (
    DOMAIN as NOTIFY_DOMAIN,
    NotifyServiceArgument,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.selector import MediaSelector

from .const import DOMAIN, SMTPService, SMTPServiceArgument

SERVICE_SEND_MESSAGE_SCHEMA = cv.make_entity_service_schema(
    {
        probatio.Optional(NotifyServiceArgument.TITLE): cv.string,
        probatio.Required(NotifyServiceArgument.MESSAGE): cv.string,
        probatio.Optional(SMTPServiceArgument.HTML): cv.string,
        probatio.Optional(SMTPServiceArgument.ATTACHMENTS): probatio.All(
            probatio.EnsureList(),
            [
                probatio.Schema(
                    {
                        probatio.Required(
                            SMTPServiceArgument.MEDIA_SOURCE
                        ): MediaSelector({"accept": ["*"]}),
                        probatio.Optional(SMTPServiceArgument.FILENAME): cv.string,
                        probatio.Optional(SMTPServiceArgument.CONTENT_ID): cv.string,
                    }
                )
            ],
        ),
        probatio.Optional(SMTPServiceArgument.PRIORITY): probatio.In(
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
        SMTPService.SEND_MESSAGE,
        entity_domain=NOTIFY_DOMAIN,
        schema=SERVICE_SEND_MESSAGE_SCHEMA,
        func="smtp_send_message",
    )
