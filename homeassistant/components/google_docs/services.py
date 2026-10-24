"""Actions to append and read Google Docs text."""

from enum import StrEnum
from typing import TYPE_CHECKING, NoReturn, cast

from aiohttp import ClientError
import gdocs_client
from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError
import probatio

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import (
    HomeAssistantError,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import DOMAIN

if TYPE_CHECKING:
    from . import GoogleDocsConfigEntry


class GoogleDocsService(StrEnum):
    """Service names."""

    APPEND_TEXT = "append_text"
    GET_TEXT = "get_text"


class GoogleDocsServiceArgument(StrEnum):
    """Service argument names."""

    CONFIG_ENTRY = "config_entry"
    TEXT = "text"


APPEND_TEXT_SCHEMA = probatio.Schema(
    {
        probatio.Required(GoogleDocsServiceArgument.CONFIG_ENTRY): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
        probatio.Required(GoogleDocsServiceArgument.TEXT): probatio.All(
            cv.string, probatio.Length(min=1)
        ),
    }
)
GET_TEXT_SCHEMA = probatio.Schema(
    {
        probatio.Required(GoogleDocsServiceArgument.CONFIG_ENTRY): ConfigEntrySelector(
            {"integration": DOMAIN}
        )
    }
)


async def _async_access_token(call: ServiceCall, entry: GoogleDocsConfigEntry) -> str:
    """Get a valid token and start reauthentication when authorization expires."""
    session = entry.runtime_data
    try:
        await session.async_ensure_token_valid()
    except OAuth2TokenRequestReauthError as err:
        entry.async_start_reauth(call.hass)
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="auth_failed"
        ) from err
    except (ClientError, OAuth2TokenRequestError, TimeoutError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err
    return cast(str, session.token[CONF_ACCESS_TOKEN])


def _raise_action_error(
    call: ServiceCall, entry: GoogleDocsConfigEntry, err: Exception, action: str
) -> NoReturn:
    """Translate Google errors without including document text in messages."""
    if isinstance(err, GoogleAuthError) or (
        isinstance(err, HttpError) and err.resp.status == 401
    ):
        entry.async_start_reauth(call.hass)
        key = "auth_failed"
    elif isinstance(err, HttpError) and err.resp.status in (403, 404):
        key = "document_not_accessible"
    else:
        key = f"{action}_failed"
    raise HomeAssistantError(translation_domain=DOMAIN, translation_key=key) from err


async def _async_append_text(call: ServiceCall) -> None:
    """Append text to the document belonging to the selected entry."""
    entry: GoogleDocsConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[GoogleDocsServiceArgument.CONFIG_ENTRY]
    )
    access_token = await _async_access_token(call, entry)
    assert entry.unique_id is not None
    try:
        await call.hass.async_add_executor_job(
            gdocs_client.append_text,
            access_token,
            entry.unique_id,
            call.data[GoogleDocsServiceArgument.TEXT],
        )
    except gdocs_client.API_ERRORS as err:
        _raise_action_error(call, entry, err, "append")


async def _async_get_text(call: ServiceCall) -> ServiceResponse:
    """Return the document's plain text as an action response."""
    entry: GoogleDocsConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[GoogleDocsServiceArgument.CONFIG_ENTRY]
    )
    access_token = await _async_access_token(call, entry)
    assert entry.unique_id is not None
    try:
        document = await call.hass.async_add_executor_job(
            gdocs_client.get_document, access_token, entry.unique_id
        )
    except gdocs_client.API_ERRORS as err:
        _raise_action_error(call, entry, err, "get")

    return {
        "document_id": entry.unique_id,
        "title": document["title"],
        "text": document["text"],
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Google Docs actions, following the Sheets integration."""
    hass.services.async_register(
        DOMAIN,
        GoogleDocsService.APPEND_TEXT,
        _async_append_text,
        schema=APPEND_TEXT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        GoogleDocsService.GET_TEXT,
        _async_get_text,
        schema=GET_TEXT_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
