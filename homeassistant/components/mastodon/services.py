"""Define services for the Mastodon integration."""

from datetime import timedelta
from enum import StrEnum
from functools import partial
from math import isfinite
from pathlib import Path
from typing import Any

from mastodon import Mastodon
from mastodon.Mastodon import (
    Account,
    MastodonAPIError,
    MastodonNotFoundError,
    MastodonUnauthorizedError,
    MediaAttachment,
)
import voluptuous as vol

from homeassistant.components import camera, image
from homeassistant.components.media_source import async_resolve_media
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, ATTR_NAME
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.selector import MediaSelector

from .const import (
    ATTR_ACCOUNT_NAME,
    ATTR_ATTRIBUTION_DOMAINS,
    ATTR_AVATAR,
    ATTR_AVATAR_MIME_TYPE,
    ATTR_BOT,
    ATTR_CONTENT_WARNING,
    ATTR_DISCOVERABLE,
    ATTR_DISPLAY_NAME,
    ATTR_DURATION,
    ATTR_FIELDS,
    ATTR_HEADER,
    ATTR_HEADER_MIME_TYPE,
    ATTR_HIDE_NOTIFICATIONS,
    ATTR_IDEMPOTENCY_KEY,
    ATTR_LANGUAGE,
    ATTR_LOCKED,
    ATTR_MEDIA,
    ATTR_MEDIA_DESCRIPTION,
    ATTR_MEDIA_WARNING,
    ATTR_NOTE,
    ATTR_QUOTE_APPROVAL_POLICY,
    ATTR_STATUS,
    ATTR_VALUE,
    ATTR_VISIBILITY,
    DOMAIN,
    LOGGER,
)
from .coordinator import MastodonConfigEntry
from .utils import get_media_type

MAX_DURATION_SECONDS = 315360000  # 10 years


class StatusVisibility(StrEnum):
    """StatusVisibility model."""

    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"
    DIRECT = "direct"


class QuoteApprovalPolicy(StrEnum):
    """QuoteApprovalPolicy model."""

    PUBLIC = "public"
    FOLLOWERS = "followers"
    NOBODY = "nobody"


SERVICE_GET_ACCOUNT = "get_account"
SERVICE_GET_ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_ACCOUNT_NAME): str,
    }
)
SERVICE_MUTE_ACCOUNT = "mute_account"
SERVICE_MUTE_ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_ACCOUNT_NAME): str,
        vol.Optional(ATTR_DURATION): vol.All(
            cv.time_period,
            vol.Range(
                min=timedelta(seconds=1), max=timedelta(seconds=MAX_DURATION_SECONDS)
            ),
        ),
        vol.Optional(ATTR_HIDE_NOTIFICATIONS, default=True): bool,
    }
)
SERVICE_UNMUTE_ACCOUNT = "unmute_account"
SERVICE_UNMUTE_ACCOUNT_SCHEMA = vol.Schema(
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
        vol.Optional(ATTR_QUOTE_APPROVAL_POLICY): vol.In(
            [x.lower() for x in QuoteApprovalPolicy]
        ),
        vol.Optional(ATTR_IDEMPOTENCY_KEY): str,
        vol.Optional(ATTR_CONTENT_WARNING): str,
        vol.Optional(ATTR_LANGUAGE): str,
        vol.Optional(ATTR_MEDIA): str,
        vol.Optional(ATTR_MEDIA_DESCRIPTION): str,
        vol.Optional(ATTR_MEDIA_WARNING): bool,
    }
)

SERVICE_UPDATE_PROFILE = "update_profile"
SERVICE_UPDATE_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Optional(ATTR_DISPLAY_NAME): str,
        vol.Optional(ATTR_NOTE): str,
        vol.Optional(ATTR_AVATAR): MediaSelector({"accept": ["image/*"]}),
        vol.Optional(ATTR_HEADER): MediaSelector({"accept": ["image/*"]}),
        vol.Optional(ATTR_LOCKED): bool,
        vol.Optional(ATTR_BOT): bool,
        vol.Optional(ATTR_DISCOVERABLE): bool,
        vol.Optional(ATTR_FIELDS): vol.All(
            cv.ensure_list, vol.Length(max=4), [dict[str, str]]
        ),
        vol.Optional(ATTR_ATTRIBUTION_DOMAINS): vol.All(cv.ensure_list, [str]),
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
        DOMAIN,
        SERVICE_MUTE_ACCOUNT,
        _async_mute_account,
        schema=SERVICE_MUTE_ACCOUNT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UNMUTE_ACCOUNT,
        _async_unmute_account,
        schema=SERVICE_UNMUTE_ACCOUNT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_POST, _async_post, schema=SERVICE_POST_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_PROFILE,
        _async_update_profile,
        schema=SERVICE_UPDATE_PROFILE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


async def _async_account_lookup(
    hass: HomeAssistant, client: Mastodon, account_name: str
) -> Account:
    """Lookup a Mastodon account by its username."""
    try:
        account: Account = await hass.async_add_executor_job(
            partial(client.account_lookup, acct=account_name)
        )
    except MastodonNotFoundError:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="account_not_found",
            translation_placeholders={"account_name": account_name},
        ) from None
    return account


async def _async_get_account(call: ServiceCall) -> ServiceResponse:
    """Get account information."""
    entry: MastodonConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    client = entry.runtime_data.client

    account_name: str = call.data[ATTR_ACCOUNT_NAME]

    try:
        account = await _async_account_lookup(call.hass, client, account_name)
    except MastodonAPIError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unable_to_get_account",
            translation_placeholders={"account_name": account_name},
        ) from err

    return {"account": account}


async def _async_mute_account(call: ServiceCall) -> ServiceResponse:
    """Mute account."""
    entry: MastodonConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    client = entry.runtime_data.client

    account_name: str = call.data[ATTR_ACCOUNT_NAME]
    hide_notifications: bool = call.data[ATTR_HIDE_NOTIFICATIONS]
    duration: int | None = None
    if call.data.get(ATTR_DURATION) is not None:
        td: timedelta = call.data[ATTR_DURATION]
        duration_seconds = td.total_seconds()

        if not isfinite(duration_seconds) or duration_seconds > MAX_DURATION_SECONDS:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="mute_duration_too_long",
            )

        duration = int(duration_seconds)

    try:
        account = await _async_account_lookup(call.hass, client, account_name)
        await call.hass.async_add_executor_job(
            partial(
                client.account_mute,
                id=account.id,
                notifications=hide_notifications,
                duration=duration,
            )
        )
    except MastodonAPIError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unable_to_mute_account",
            translation_placeholders={"account_name": account_name},
        ) from err

    return None


async def _async_unmute_account(call: ServiceCall) -> ServiceResponse:
    """Unmute account."""
    entry: MastodonConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    client = entry.runtime_data.client

    account_name: str = call.data[ATTR_ACCOUNT_NAME]

    try:
        account = await _async_account_lookup(call.hass, client, account_name)
        await call.hass.async_add_executor_job(
            partial(client.account_unmute, id=account.id)
        )
    except MastodonAPIError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unable_to_unmute_account",
            translation_placeholders={"account_name": account_name},
        ) from err

    return None


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
    quote_approval_policy: str | None = (
        QuoteApprovalPolicy(call.data[ATTR_QUOTE_APPROVAL_POLICY])
        if ATTR_QUOTE_APPROVAL_POLICY in call.data
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
            quote_approval_policy=quote_approval_policy,
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


async def _async_update_profile(call: ServiceCall) -> ServiceResponse:
    """Update profile information."""
    params = dict(call.data.copy())

    entry: MastodonConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, params.pop(ATTR_CONFIG_ENTRY_ID)
    )
    client = entry.runtime_data.client

    if avatar := params.pop(ATTR_AVATAR, None):
        params[ATTR_AVATAR], params[ATTR_AVATAR_MIME_TYPE] = await _resolve_media(
            call.hass, avatar
        )
    if header := params.pop(ATTR_HEADER, None):
        params[ATTR_HEADER], params[ATTR_HEADER_MIME_TYPE] = await _resolve_media(
            call.hass, header
        )
    if fields := params.get(ATTR_FIELDS):
        params[ATTR_FIELDS] = [
            (field[ATTR_NAME].strip(), field[ATTR_VALUE].strip())
            for field in fields
            if field[ATTR_NAME].strip()
        ]
    try:
        return await call.hass.async_add_executor_job(
            lambda: client.account_update_credentials(**params)
        )
    except MastodonUnauthorizedError as error:
        entry.async_start_reauth(call.hass)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="auth_failed",
        ) from error
    except MastodonAPIError as err:
        LOGGER.debug("Full exception:", exc_info=err)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unable_to_update_profile",
        ) from err


async def _resolve_media(
    hass: HomeAssistant, media_source: dict[str, str]
) -> tuple[bytes | Path, str | None]:
    """Resolve media from a media source."""
    media_content_id: str = media_source["media_content_id"]
    if media_content_id.startswith("media-source://camera/"):
        entity_id = media_content_id.removeprefix("media-source://camera/")
        snapshot = await camera.async_get_image(hass, entity_id)
        return snapshot.content, snapshot.content_type

    if media_content_id.startswith("media-source://image/"):
        entity_id = media_content_id.removeprefix("media-source://image/")
        img = await image.async_get_image(hass, entity_id)
        return img.content, img.content_type

    media = await async_resolve_media(hass, media_source["media_content_id"], None)

    if media.path is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="media_source_not_supported",
            translation_placeholders={"media_content_id": media_content_id},
        )

    return media.path, media.mime_type
