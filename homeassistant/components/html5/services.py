"""Service registration for HTML5 integration."""

import probatio

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    DOMAIN as NOTIFY_DOMAIN,
)
from homeassistant.const import ATTR_ICON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    ATTR_ACTION,
    ATTR_ACTIONS,
    ATTR_BADGE,
    ATTR_DIR,
    ATTR_IMAGE,
    ATTR_LANG,
    ATTR_RENOTIFY,
    ATTR_REQUIRE_INTERACTION,
    ATTR_SILENT,
    ATTR_TAG,
    ATTR_TIMESTAMP,
    ATTR_TTL,
    ATTR_URGENCY,
    ATTR_VIBRATE,
    DOMAIN,
)

SERVICE_SEND_MESSAGE = "send_message"
SERVICE_DISMISS_MESSAGE = "dismiss_message"

SERVICE_SEND_MESSAGE_SCHEMA = cv.make_entity_service_schema(
    {
        probatio.Required(ATTR_TITLE, default=ATTR_TITLE_DEFAULT): cv.string,
        probatio.Optional(ATTR_MESSAGE): cv.string,
        probatio.Optional(ATTR_DIR): probatio.In({"auto", "ltr", "rtl"}),
        probatio.Optional(ATTR_ICON): cv.string,
        probatio.Optional(ATTR_BADGE): cv.string,
        probatio.Optional(ATTR_IMAGE): cv.string,
        probatio.Optional(ATTR_TAG): cv.string,
        probatio.Exclusive(ATTR_VIBRATE, "silent_xor_vibrate"): probatio.All(
            cv.ensure_list,
            [probatio.All(probatio.Coerce(int), probatio.Range(min=0))],
        ),
        probatio.Optional(ATTR_TIMESTAMP): cv.datetime,
        probatio.Optional(ATTR_LANG): cv.language,
        probatio.Exclusive(ATTR_SILENT, "silent_xor_vibrate"): cv.boolean,
        probatio.Optional(ATTR_RENOTIFY): cv.boolean,
        probatio.Optional(ATTR_REQUIRE_INTERACTION): cv.boolean,
        probatio.Optional(ATTR_URGENCY): probatio.In({"normal", "high", "low"}),
        probatio.Optional(ATTR_TTL): probatio.All(
            cv.time_period, cv.positive_timedelta
        ),
        probatio.Optional(ATTR_ACTIONS): probatio.All(
            cv.ensure_list,
            [
                {
                    probatio.Required(ATTR_ACTION): cv.string,
                    probatio.Required(ATTR_TITLE): cv.string,
                    probatio.Optional(ATTR_ICON): cv.string,
                }
            ],
        ),
        probatio.Optional(ATTR_DATA): dict,
    }
)

SERVICE_DISMISS_MESSAGE_SCHEMA = cv.make_entity_service_schema(
    {probatio.Optional(ATTR_TAG): cv.string}
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for HTML5 integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        entity_domain=NOTIFY_DOMAIN,
        schema=SERVICE_SEND_MESSAGE_SCHEMA,
        func="send_push_notification",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_DISMISS_MESSAGE,
        entity_domain=NOTIFY_DOMAIN,
        schema=SERVICE_DISMISS_MESSAGE_SCHEMA,
        func="dismiss_notification",
    )
