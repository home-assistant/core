"""Support for Google Docs."""

from aiohttp import ClientError
import gdocs_client
from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_ACCESS, DOMAIN
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type GoogleDocsConfigEntry = ConfigEntry[OAuth2Session]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the Google Docs actions."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GoogleDocsConfigEntry) -> None:
    """Set up Google Docs from a configuration entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except OAuth2TokenRequestReauthError as err:
        raise ConfigEntryAuthFailed("Google account authorization expired") from err
    except (ClientError, OAuth2TokenRequestError, TimeoutError) as err:
        raise ConfigEntryNotReady("Unable to refresh Google authorization") from err

    if DEFAULT_ACCESS not in entry.data.get(CONF_TOKEN, {}).get("scope", "").split():
        raise ConfigEntryAuthFailed("Required Google Docs permission was not granted")

    assert entry.unique_id is not None
    try:
        await hass.async_add_executor_job(
            gdocs_client.get_document,
            session.token[CONF_ACCESS_TOKEN],
            entry.unique_id,
            False,
        )
    except GoogleAuthError as err:
        raise ConfigEntryAuthFailed("Google account authorization expired") from err
    except HttpError as err:
        if err.resp.status == 401:
            raise ConfigEntryAuthFailed("Google account authorization expired") from err
        if err.resp.status == 429 or err.resp.status >= 500:
            raise ConfigEntryNotReady("Google Docs is temporarily unavailable") from err
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="document_not_accessible"
        ) from err
    except gdocs_client.API_ERRORS as err:
        raise ConfigEntryNotReady("Unable to connect to Google Docs") from err

    entry.runtime_data = session


async def async_unload_entry(hass: HomeAssistant, entry: GoogleDocsConfigEntry) -> None:
    """Unload a configuration entry without deleting its Google document."""
