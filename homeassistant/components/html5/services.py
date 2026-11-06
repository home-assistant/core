"""Service registration for HTML5 integration."""

from enum import StrEnum

import probatio

from homeassistant.components.notify import (
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    DOMAIN as NOTIFY_DOMAIN,
)
from homeassistant.const import ATTR_ICON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import ATTR_ACTION, DOMAIN


class HTML5Service(StrEnum):
    """Store keys for HTML5 services."""

    SEND_MESSAGE = "send_message"
    DISMISS_MESSAGE = "dismiss_message"


class HTML5ServiceArgument(StrEnum):
    """Store keys for HTML5 service arguments."""

    TITLE = "title"
    MESSAGE = "message"
    ICON = "icon"
    BADGE = "badge"
    IMAGE = "image"
    TAG = "tag"
    ACTIONS = "actions"
    DIR = "dir"
    RENOTIFY = "renotify"
    SILENT = "silent"
    REQUIRE_INTERACTION = "require_interaction"
    VIBRATE = "vibrate"
    LANG = "lang"
    TIMESTAMP = "timestamp"
    TTL = "ttl"
    URGENCY = "urgency"
    DATA = "data"


SERVICE_SEND_MESSAGE_SCHEMA = cv.make_entity_service_schema(
    {
        probatio.Required(
            HTML5ServiceArgument.TITLE, default=ATTR_TITLE_DEFAULT
        ): cv.string,
        probatio.Optional(HTML5ServiceArgument.MESSAGE): cv.string,
        probatio.Optional(HTML5ServiceArgument.DIR): probatio.In(
            {"auto", "ltr", "rtl"}
        ),
        probatio.Optional(HTML5ServiceArgument.ICON): cv.string,
        probatio.Optional(HTML5ServiceArgument.BADGE): cv.string,
        probatio.Optional(HTML5ServiceArgument.IMAGE): cv.string,
        probatio.Optional(HTML5ServiceArgument.TAG): cv.string,
        probatio.Exclusive(
            HTML5ServiceArgument.VIBRATE, "silent_xor_vibrate"
        ): probatio.All(
            probatio.EnsureList(),
            [probatio.All(probatio.Coerce(int), probatio.Range(min=0))],
        ),
        probatio.Optional(HTML5ServiceArgument.TIMESTAMP): cv.datetime,
        probatio.Optional(HTML5ServiceArgument.LANG): cv.language,
        probatio.Exclusive(
            HTML5ServiceArgument.SILENT, "silent_xor_vibrate"
        ): cv.boolean,
        probatio.Optional(HTML5ServiceArgument.RENOTIFY): cv.boolean,
        probatio.Optional(HTML5ServiceArgument.REQUIRE_INTERACTION): cv.boolean,
        probatio.Optional(HTML5ServiceArgument.URGENCY): probatio.In(
            {"normal", "high", "low"}
        ),
        probatio.Optional(HTML5ServiceArgument.TTL): probatio.All(
            cv.time_period, cv.positive_timedelta
        ),
        probatio.Optional(HTML5ServiceArgument.ACTIONS): probatio.All(
            probatio.EnsureList(),
            [
                {
                    probatio.Required(ATTR_ACTION): cv.string,
                    probatio.Required(ATTR_TITLE): cv.string,
                    probatio.Optional(ATTR_ICON): cv.string,
                }
            ],
        ),
        probatio.Optional(HTML5ServiceArgument.DATA): dict,
    }
)

SERVICE_DISMISS_MESSAGE_SCHEMA = cv.make_entity_service_schema(
    {probatio.Optional(HTML5ServiceArgument.TAG): cv.string}
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for HTML5 integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        HTML5Service.SEND_MESSAGE,
        entity_domain=NOTIFY_DOMAIN,
        schema=SERVICE_SEND_MESSAGE_SCHEMA,
        func="send_push_notification",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        HTML5Service.DISMISS_MESSAGE,
        entity_domain=NOTIFY_DOMAIN,
        schema=SERVICE_DISMISS_MESSAGE_SCHEMA,
        func="dismiss_notification",
    )
