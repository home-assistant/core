"""Define services for the Mastodon integration."""

from enum import StrEnum
from functools import partial
from typing import Any

from mastodon import Mastodon
from mastodon.Mastodon import Account, MastodonAPIError, MediaAttachment
import voluptuous as vol

from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import service

from .const import (
    ATTR_ACCOUNT_NAME,
    ATTR_CONTENT_WARNING,
    ATTR_IDEMPOTENCY_KEY,
    ATTR_LANGUAGE,
    ATTR_MEDIA,
    ATTR_MEDIA_DESCRIPTION,
    ATTR_MEDIA_WARNING,
    ATTR_STATUS,
    ATTR_VISIBILITY,
    DOMAIN,
)
from .coordinator import MastodonConfigEntry
from .utils import get_media_type


class StatusVisibility(StrEnum):
    """StatusVisibility model."""

    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"
    DIRECT = "direct"


SERVICE_GET_ACCOUNT = "get_account"
SERVICE_GET_ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_ACCOUNT_NAME): str,
    }
)
SERVICE_POST = "post"
SERVICE_POST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_STATUS): str,
        vol.Optional(ATTR_VISIBILITY): vol.In([x.lower() for x in StatusVisibility]),
        vol.Optional(ATTR_IDEMPOTENCY_KEY): str,
        vol.Optional(ATTR_CONTENT_WARNING): str,
        vol.Optional(ATTR_LANGUAGE): str,
        vol.Optional(ATTR_MEDIA): str,
        vol.Optional(ATTR_MEDIA_DESCRIPTION): str,
        vol.Optional(ATTR_MEDIA_WARNING): bool,
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Mastodon integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ACCOUNT,
        _async_get_account,
        schema=SERVICE_GET_ACCOUNT_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_POST, _async_post, schema=SERVICE_POST_SCHEMA
    )


async def _async_get_account(call: ServiceCall) -> ServiceResponse:
    """Get account information."""
    entry: MastodonConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    client = entry.runtime_data.client

    account_name: str = call.data[ATTR_ACCOUNT_NAME]

    try:
        account: Account = await call.hass.async_add_executor_job(
            partial(client.account_lookup, acct=account_name)
        )
    except MastodonAPIError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unable_to_get_account",
            translation_placeholders={"account_name": account_name},
        ) from err

    return {"account": account}


async def _async_post(call: ServiceCall) -> ServiceResponse:
    """Post a status."""
    entry: MastodonConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    client = entry.runtime_data.client

    status: str = call.data[ATTR_STATUS]

    visibility: str | None = (
        StatusVisibility(call.data[ATTR_VISIBILITY])
        if ATTR_VISIBILITY in call.data
        else None
    )
    idempotency_key: str | None = call.data.get(ATTR_IDEMPOTENCY_KEY)
    spoiler_text: str | None = call.data.get(ATTR_CONTENT_WARNING)
    language: str | None = call.data.get(ATTR_LANGUAGE)
    media_path: str | None = call.data.get(ATTR_MEDIA)
    media_description: str | None = call.data.get(ATTR_MEDIA_DESCRIPTION)
    media_warning: str | None = call.data.get(ATTR_MEDIA_WARNING)

    if idempotency_key and len(idempotency_key) < 4:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="idempotency_key_too_short",
        )

    await call.hass.async_add_executor_job(
        partial(
            _post,
            hass=call.hass,
            client=client,
            status=status,
            visibility=visibility,
            idempotency_key=idempotency_key,
            spoiler_text=spoiler_text,
            language=language,
            media_path=media_path,
            media_description=media_description,
            sensitive=media_warning,
        )
    )

    return None


def _post(hass: HomeAssistant, client: Mastodon, **kwargs: Any) -> None:
    """Post to Mastodon."""

    media_data: MediaAttachment | None = None

    media_path = kwargs.get("media_path")
    if media_path:
        if not hass.config.is_allowed_path(media_path):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="not_whitelisted_directory",
                translation_placeholders={"media": media_path},
            )

        media_type = get_media_type(media_path)
        media_description = kwargs.get("media_description")
        try:
            media_data = client.media_post(
                media_file=media_path,
                mime_type=media_type,
                description=media_description,
            )

        except MastodonAPIError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unable_to_upload_image",
                translation_placeholders={"media_path": media_path},
            ) from err

    kwargs.pop("media_path", None)
    kwargs.pop("media_description", None)

    media_ids: str | None = None
    if media_data:
        media_ids = media_data.id
    try:
        client.status_post(media_ids=media_ids, **kwargs)
    except MastodonAPIError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unable_to_send_message",
        ) from err
