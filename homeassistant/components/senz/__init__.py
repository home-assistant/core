"""The nVent RAYCHEM SENZ integration."""

from __future__ import annotations

from http import HTTPStatus
import logging

from aiohttp import ClientResponseError
from httpx import HTTPStatusError, RequestError
import jwt
from pysenz import SENZAPI

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, httpx_client
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import SENZConfigEntryAuth
from .const import DOMAIN
from .coordinator import SENZConfigEntry, SENZDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SENZConfigEntry) -> bool:
    """Set up SENZ from a config entry."""
    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err
    session = OAuth2Session(hass, entry, implementation)
    auth = SENZConfigEntryAuth(httpx_client.get_async_client(hass), session)
    senz_api = SENZAPI(auth)

    try:
        account = await senz_api.get_account()
    except HTTPStatusError as err:
        if err.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="config_entry_auth_failed",
            ) from err
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_ready",
        ) from err
    except ClientResponseError as err:
        if err.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.BAD_REQUEST):
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="config_entry_auth_failed",
            ) from err
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_ready",
        ) from err
    except RequestError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_ready",
        ) from err
    except Exception as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="config_entry_auth_failed",
        ) from err

    coordinator = SENZDataUpdateCoordinator(
        hass,
        entry,
        name=account.username,
        senz_api=senz_api,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SENZConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: SENZConfigEntry
) -> bool:
    """Migrate old entry."""

    # Use sub(ject) from access_token as unique_id
    if config_entry.version == 1 and config_entry.minor_version == 1:
        token = jwt.decode(
            config_entry.data["token"]["access_token"],
            options={"verify_signature": False},
        )
        uid = token["sub"]
        hass.config_entries.async_update_entry(
            config_entry, unique_id=uid, minor_version=2
        )
        _LOGGER.info(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
        )

    return True
