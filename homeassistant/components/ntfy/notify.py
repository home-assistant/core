"""ntfy notification entity."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from aiontfy import Message
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
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_TOPIC, DOMAIN
from .coordinator import NtfyConfigEntry

PARALLEL_UPDATES = 0


SERVICE_PUBLISH = "publish"
ATTR_ATTACH = "attach"
ATTR_CALL = "call"
ATTR_CLICK = "click"
ATTR_DELAY = "delay"
ATTR_EMAIL = "email"
ATTR_ICON = "icon"
ATTR_MARKDOWN = "markdown"
ATTR_PRIORITY = "priority"
ATTR_TAGS = "tags"

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
    )


class NtfyNotifyEntity(NotifyEntity):
    """Representation of a ntfy notification entity."""

    entity_description = NotifyEntityDescription(
        key="publish",
        translation_key="publish",
        name=None,
        has_entity_name=True,
    )
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(
        self,
        config_entry: NtfyConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize a notification entity."""

        self._attr_unique_id = f"{config_entry.entry_id}_{subentry.subentry_id}_{self.entity_description.key}"
        self.topic = subentry.data[CONF_TOPIC]

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="ntfy LLC",
            model="ntfy",
            name=subentry.data.get(CONF_NAME, self.topic),
            configuration_url=URL(config_entry.data[CONF_URL]) / self.topic,
            identifiers={(DOMAIN, f"{config_entry.entry_id}_{subentry.subentry_id}")},
            via_device=(DOMAIN, config_entry.entry_id),
        )
        self.config_entry = config_entry
        self.ntfy = config_entry.runtime_data.ntfy

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
