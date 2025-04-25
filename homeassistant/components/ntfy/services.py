"""Actions for the ntfy integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, cast

from aiontfy import Message
from aiontfy.exceptions import NtfyException, NtfyHTTPError
import voluptuous as vol
from yarl import URL

from homeassistant.components.notify import ATTR_MESSAGE, ATTR_TITLE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import (
    ATTR_ATTACH,
    ATTR_CALL,
    ATTR_CLICK,
    ATTR_DELAY,
    ATTR_EMAIL,
    ATTR_ICON,
    ATTR_MARKDOWN,
    ATTR_PRIORITY,
    ATTR_TAGS,
    CONF_TOPIC,
    DOMAIN,
    SERVICE_PUBLISH,
)
from .typedefs import NtfyConfigEntry

SERVICE_PUBLISH_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
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


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up action for ntfy integration."""

    async def publish(call: ServiceCall) -> None:
        """Publish a message to a topic."""

        params = dict(call.data)
        entity_id = params.pop(ATTR_ENTITY_ID)

        delay: timedelta | None = params.get("delay")
        if delay:
            params["delay"] = (
                f"{delay.days}d {delay.seconds}s" if delay.days else f"{delay.seconds}s"
            )

        if not (entity := er.async_get(hass).async_get(entity_id)):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entity_not_found",
            )

        config_entry_id = entity.config_entry_id
        subentry_id = entity.config_subentry_id
        if TYPE_CHECKING:
            assert config_entry_id
            assert subentry_id
        config_entry = cast(
            NtfyConfigEntry, hass.config_entries.async_get_entry(config_entry_id)
        )
        if config_entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_loaded",
            )

        ntfy = config_entry.runtime_data
        topic: str = config_entry.subentries[subentry_id].data[CONF_TOPIC]

        msg = Message(topic=topic, **params)
        try:
            await ntfy.publish(msg)
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

    hass.services.async_register(
        DOMAIN,
        SERVICE_PUBLISH,
        publish,
        schema=SERVICE_PUBLISH_SCHEMA,
    )
