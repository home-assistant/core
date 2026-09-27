"""Service registration for ntfy integration."""

from datetime import timedelta
from typing import Any

from aiontfy import BroadcastAction, CopyAction, HttpAction, ViewAction
import probatio
from yarl import URL

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
)
from homeassistant.const import ATTR_ICON
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
ATTR_MARKDOWN = "markdown"
ATTR_PRIORITY = "priority"
ATTR_TAGS = "tags"
ATTR_SEQUENCE_ID = "sequence_id"
ATTR_ATTACH_FILE = "attach_file"
ATTR_FILENAME = "filename"
GRP_ATTACHMENT = "attachment"
MSG_ATTACHMENT = "Only one attachment source is allowed: URL or local file"
ATTR_ACTIONS = "actions"
ATTR_ACTION = "action"
ATTR_VIEW = "view"
ATTR_BROADCAST = "broadcast"
ATTR_HTTP = "http"
ATTR_LABEL = "label"
ATTR_URL = "url"
ATTR_CLEAR = "clear"
ATTR_INTENT = "intent"
ATTR_EXTRAS = "extras"
ATTR_METHOD = "method"
ATTR_HEADERS = "headers"
ATTR_BODY = "body"
ATTR_VALUE = "value"
ATTR_COPY = "copy"
ACTIONS_MAP = {
    ATTR_VIEW: ViewAction,
    ATTR_BROADCAST: BroadcastAction,
    ATTR_HTTP: HttpAction,
    ATTR_COPY: CopyAction,
}
MAX_ACTIONS_ALLOWED = 3  # ntfy only supports up to 3 actions per notification


def validate_filename(params: dict[str, Any]) -> dict[str, Any]:
    """Validate filename."""
    if ATTR_FILENAME in params and not (
        ATTR_ATTACH_FILE in params or ATTR_ATTACH in params
    ):
        raise probatio.Invalid("Filename only allowed when attachment is provided")
    return params


ACTION_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_LABEL): cv.string,
        probatio.Optional(ATTR_CLEAR, default=False): cv.boolean,
    }
)
VIEW_SCHEMA = ACTION_SCHEMA.extend(
    {
        probatio.Required(ATTR_ACTION): probatio.Equal("view"),
        probatio.Required(ATTR_URL): probatio.All(probatio.Url(), probatio.Coerce(URL)),
    }
)
BROADCAST_SCHEMA = ACTION_SCHEMA.extend(
    {
        probatio.Required(ATTR_ACTION): probatio.Equal("broadcast"),
        probatio.Optional(ATTR_INTENT): cv.string,
        probatio.Optional(ATTR_EXTRAS): dict[str, str],
    }
)
HTTP_SCHEMA = VIEW_SCHEMA.extend(
    {
        probatio.Required(ATTR_ACTION): probatio.Equal("http"),
        probatio.Optional(ATTR_METHOD): cv.string,
        probatio.Optional(ATTR_HEADERS): dict[str, str],
        probatio.Optional(ATTR_BODY): cv.string,
    }
)
COPY_SCHEMA = ACTION_SCHEMA.extend(
    {
        probatio.Required(ATTR_ACTION): probatio.Equal("copy"),
        probatio.Required(ATTR_VALUE): cv.string,
    }
)

SERVICE_PUBLISH_SCHEMA = probatio.All(
    cv.make_entity_service_schema(
        {
            probatio.Optional(ATTR_TITLE): cv.string,
            probatio.Optional(ATTR_MESSAGE): cv.string,
            probatio.Optional(ATTR_MARKDOWN): cv.boolean,
            probatio.Optional(ATTR_TAGS): probatio.All(cv.ensure_list, [str]),
            probatio.Optional(ATTR_PRIORITY): probatio.All(
                probatio.Coerce(int), probatio.Range(1, 5)
            ),
            probatio.Optional(ATTR_CLICK): probatio.All(
                probatio.Url(), probatio.Coerce(URL)
            ),
            probatio.Optional(ATTR_DELAY): probatio.All(
                cv.time_period,
                probatio.Range(min=timedelta(seconds=10), max=timedelta(days=3)),
            ),
            probatio.Optional(ATTR_EMAIL): probatio.Email(),
            probatio.Optional(ATTR_CALL): cv.string,
            probatio.Optional(ATTR_ICON): probatio.All(
                probatio.Url(), probatio.Coerce(URL)
            ),
            probatio.Optional(ATTR_SEQUENCE_ID): cv.string,
            probatio.Exclusive(
                ATTR_ATTACH, GRP_ATTACHMENT, MSG_ATTACHMENT
            ): probatio.All(probatio.Url(), probatio.Coerce(URL)),
            probatio.Exclusive(
                ATTR_ATTACH_FILE, GRP_ATTACHMENT, MSG_ATTACHMENT
            ): MediaSelector({"accept": ["*/*"]}),
            probatio.Optional(ATTR_FILENAME): cv.string,
            probatio.Optional(ATTR_ACTIONS): probatio.All(
                cv.ensure_list,
                probatio.Length(
                    max=MAX_ACTIONS_ALLOWED,
                    msg="Too many actions defined. A maximum of 3 is supported",
                ),
                [probatio.Any(VIEW_SCHEMA, BROADCAST_SCHEMA, HTTP_SCHEMA, COPY_SCHEMA)],
            ),
        }
    ),
    validate_filename,
)

SERVICE_CLEAR_DELETE_SCHEMA = cv.make_entity_service_schema(
    {
        probatio.Required(ATTR_SEQUENCE_ID): cv.string,
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
