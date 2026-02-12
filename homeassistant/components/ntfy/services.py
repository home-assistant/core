"""Service registration for ntfy integration."""

from datetime import timedelta
from typing import Any

import voluptuous as vol
from yarl import URL

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.selector import MediaSelector

from .const import DOMAIN

SERVICE_PUBLISH = "publish"
SERVICE_CLEAR = "clear"
SERVICE_DELETE = "delete"
ATTR_ATTACH = "attach"
ATTR_CALL = "call"
ATTR_CLICK = "click"
ATTR_DELAY = "delay"
ATTR_EMAIL = "email"
ATTR_ICON = "icon"
ATTR_MARKDOWN = "markdown"
ATTR_PRIORITY = "priority"
ATTR_TAGS = "tags"
ATTR_SEQUENCE_ID = "sequence_id"
ATTR_ATTACH_FILE = "attach_file"
ATTR_FILENAME = "filename"
GRP_ATTACHMENT = "attachment"
MSG_ATTACHMENT = "Only one attachment source is allowed: URL or local file"


def validate_filename(params: dict[str, Any]) -> dict[str, Any]:
    """Validate filename."""
    if ATTR_FILENAME in params and not (
        ATTR_ATTACH_FILE in params or ATTR_ATTACH in params
    ):
        raise vol.Invalid("Filename only allowed when attachment is provided")
    return params


SERVICE_PUBLISH_SCHEMA = vol.All(
    cv.make_entity_service_schema(
        {
            vol.Optional(ATTR_TITLE): cv.string,
            vol.Optional(ATTR_MESSAGE): cv.string,
            vol.Optional(ATTR_MARKDOWN): cv.boolean,
            vol.Optional(ATTR_TAGS): vol.All(cv.ensure_list, [str]),
            vol.Optional(ATTR_PRIORITY): vol.All(vol.Coerce(int), vol.Range(1, 5)),
            vol.Optional(ATTR_CLICK): vol.All(vol.Url(), vol.Coerce(URL)),
            vol.Optional(ATTR_DELAY): vol.All(
                cv.time_period,
                vol.Range(min=timedelta(seconds=10), max=timedelta(days=3)),
            ),
            vol.Optional(ATTR_EMAIL): vol.Email(),
            vol.Optional(ATTR_CALL): cv.string,
            vol.Optional(ATTR_ICON): vol.All(vol.Url(), vol.Coerce(URL)),
            vol.Optional(ATTR_SEQUENCE_ID): cv.string,
            vol.Exclusive(ATTR_ATTACH, GRP_ATTACHMENT, MSG_ATTACHMENT): vol.All(
                vol.Url(), vol.Coerce(URL)
            ),
            vol.Exclusive(
                ATTR_ATTACH_FILE, GRP_ATTACHMENT, MSG_ATTACHMENT
            ): MediaSelector({"accept": ["*/*"]}),
            vol.Optional(ATTR_FILENAME): cv.string,
        }
    ),
    validate_filename,
)

SERVICE_CLEAR_DELETE_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required(ATTR_SEQUENCE_ID): cv.string,
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for ntfy integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_PUBLISH,
        entity_domain=NOTIFY_DOMAIN,
        schema=SERVICE_PUBLISH_SCHEMA,
        description_placeholders={
            "markdown_guide_url": "https://www.markdownguide.org/basic-syntax/",
            "emoji_reference_url": "https://docs.ntfy.sh/emojis/",
        },
        func="publish",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAR,
        entity_domain=NOTIFY_DOMAIN,
        schema=SERVICE_CLEAR_DELETE_SCHEMA,
        func="clear",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_DELETE,
        entity_domain=NOTIFY_DOMAIN,
        schema=SERVICE_CLEAR_DELETE_SCHEMA,
        func="delete",
    )
