"""ntfy notification entity."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from aiontfy import BroadcastAction, HttpAction, Message, ViewAction
from aiontfy.exceptions import (
    NtfyException,
    NtfyHTTPError,
    NtfyUnauthorizedAuthenticationError,
)
import voluptuous as vol
from yarl import URL

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    NotifyEntity,
    NotifyEntityDescription,
    NotifyEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import NtfyConfigEntry
from .entity import NtfyBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
MAX_ACTIONS_ALLOWED = 3  # ntfy only supports up to 3 actions per notification

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
ACTIONS_MAP = {
    ATTR_VIEW: ViewAction,
    ATTR_BROADCAST: BroadcastAction,
    ATTR_HTTP: HttpAction,
}

ACTION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_LABEL): cv.string,
        vol.Optional(ATTR_CLEAR, default=False): cv.boolean,
    }
)
VIEW_SCHEMA = ACTION_SCHEMA.extend(
    {
        vol.Optional(ATTR_ACTION): vol.All(str, "view"),
        vol.Required(ATTR_URL): cv.url,
    }
)
BROADCAST_SCHEMA = ACTION_SCHEMA.extend(
    {
        vol.Optional(ATTR_ACTION): vol.All(str, "broadcast"),
        vol.Optional(ATTR_INTENT): cv.string,
        vol.Optional(ATTR_EXTRAS): dict[str, str],
    }
)
HTTP_SCHEMA = VIEW_SCHEMA.extend(
    {
        vol.Optional(ATTR_ACTION): vol.All(str, "http"),
        vol.Optional(ATTR_METHOD): cv.string,
        vol.Optional(ATTR_HEADERS): dict[str, str],
        vol.Optional(ATTR_BODY): cv.string,
    }
)
SERVICE_PUBLISH_SCHEMA = cv.make_entity_service_schema(
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
        vol.Optional(ATTR_ATTACH): vol.All(vol.Url(), vol.Coerce(URL)),
        vol.Optional(ATTR_EMAIL): vol.Email(),
        vol.Optional(ATTR_CALL): cv.string,
        vol.Optional(ATTR_ICON): vol.All(vol.Url(), vol.Coerce(URL)),
        vol.Optional(ATTR_SEQUENCE_ID): cv.string,
        vol.Optional(ATTR_ACTIONS): vol.All(
            cv.ensure_list, [vol.Any(VIEW_SCHEMA, BROADCAST_SCHEMA, HTTP_SCHEMA)]
        ),
    }
)

SERVICE_CLEAR_DELETE_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required(ATTR_SEQUENCE_ID): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NtfyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ntfy notification entity platform."""

    for subentry_id, subentry in config_entry.subentries.items():
        async_add_entities(
            [NtfyNotifyEntity(config_entry, subentry)], config_subentry_id=subentry_id
        )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_PUBLISH,
        SERVICE_PUBLISH_SCHEMA,
        "publish",
        description_placeholders={
            "markdown_guide_url": "https://www.markdownguide.org/basic-syntax/",
            "emoji_reference_url": "https://docs.ntfy.sh/emojis/",
        },
    )

    platform.async_register_entity_service(
        SERVICE_CLEAR,
        SERVICE_CLEAR_DELETE_SCHEMA,
        "clear",
    )

    platform.async_register_entity_service(
        SERVICE_DELETE,
        SERVICE_CLEAR_DELETE_SCHEMA,
        "delete",
    )


class NtfyNotifyEntity(NtfyBaseEntity, NotifyEntity):
    """Representation of a ntfy notification entity."""

    entity_description = NotifyEntityDescription(
        key="publish",
        translation_key="publish",
        name=None,
    )
    _attr_supported_features = NotifyEntityFeature.TITLE

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Publish a message to a topic."""
        await self.publish(message=message, title=title)

    async def publish(self, **kwargs: Any) -> None:
        """Publish a message to a topic."""

        params: dict[str, Any] = kwargs
        delay: timedelta | None = params.get("delay")
        if delay:
            params["delay"] = f"{delay.total_seconds()}s"
            if params.get("email"):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="delay_no_email",
                )
            if params.get("call"):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="delay_no_call",
                )

        actions: list[dict[str, Any]] | None = params.get(ATTR_ACTIONS)
        if actions:
            if len(actions) > MAX_ACTIONS_ALLOWED:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="too_many_actions",
                )
            params["actions"] = [
                ACTIONS_MAP[action.pop(ATTR_ACTION)](**action) for action in actions
            ]

        msg = Message(topic=self.topic, **params)
        try:
            await self.ntfy.publish(msg)
        except NtfyUnauthorizedAuthenticationError as e:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from e
        except NtfyHTTPError as e:
            raise HomeAssistantError(
                translation_key="publish_failed_request_error",
                translation_domain=DOMAIN,
                translation_placeholders={"error_msg": e.error},
            ) from e
        except NtfyException as e:
            raise HomeAssistantError(
                translation_key="publish_failed_exception",
                translation_domain=DOMAIN,
            ) from e

    async def clear(self, **kwargs: Any) -> None:
        """Clear a message."""

        params: dict[str, Any] = kwargs

        try:
            await self.ntfy.clear(self.topic, params[ATTR_SEQUENCE_ID])
        except NtfyUnauthorizedAuthenticationError as e:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from e
        except NtfyException as e:
            _LOGGER.debug("Exception:", exc_info=True)
            raise HomeAssistantError(
                translation_key="clear_failed",
                translation_domain=DOMAIN,
            ) from e

    async def delete(self, **kwargs: Any) -> None:
        """Delete a message."""

        params: dict[str, Any] = kwargs

        try:
            await self.ntfy.delete(self.topic, params[ATTR_SEQUENCE_ID])
        except NtfyUnauthorizedAuthenticationError as e:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from e
        except NtfyException as e:
            _LOGGER.debug("Exception:", exc_info=True)
            raise HomeAssistantError(
                translation_key="delete_failed",
                translation_domain=DOMAIN,
            ) from e
