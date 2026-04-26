"""Service registration for HTML5 integration."""

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    DOMAIN as NOTIFY_DOMAIN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    ATTR_ACTION,
    ATTR_ACTIONS,
    ATTR_BADGE,
    ATTR_DIR,
    ATTR_ICON,
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
        vol.Required(ATTR_TITLE, default=ATTR_TITLE_DEFAULT): cv.string,
        vol.Optional(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_DIR): vol.In({"auto", "ltr", "rtl"}),
        vol.Optional(ATTR_ICON): cv.string,
        vol.Optional(ATTR_BADGE): cv.string,
        vol.Optional(ATTR_IMAGE): cv.string,
        vol.Optional(ATTR_TAG): cv.string,
        vol.Exclusive(ATTR_VIBRATE, "silent_xor_vibrate"): vol.All(
            cv.ensure_list,
            [vol.All(vol.Coerce(int), vol.Range(min=0))],
        ),
        vol.Optional(ATTR_TIMESTAMP): cv.datetime,
        vol.Optional(ATTR_LANG): cv.language,
        vol.Exclusive(ATTR_SILENT, "silent_xor_vibrate"): cv.boolean,
        vol.Optional(ATTR_RENOTIFY): cv.boolean,
        vol.Optional(ATTR_REQUIRE_INTERACTION): cv.boolean,
        vol.Optional(ATTR_URGENCY): vol.In({"normal", "high", "low"}),
        vol.Optional(ATTR_TTL): vol.All(cv.time_period, cv.positive_timedelta),
        vol.Optional(ATTR_ACTIONS): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(ATTR_ACTION): cv.string,
                    vol.Required(ATTR_TITLE): cv.string,
                    vol.Optional(ATTR_ICON): cv.string,
                }
            ],
        ),
        vol.Optional(ATTR_DATA): dict,
    }
)

SERVICE_DISMISS_MESSAGE_SCHEMA = cv.make_entity_service_schema(
    {vol.Optional(ATTR_TAG): cv.string}
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
