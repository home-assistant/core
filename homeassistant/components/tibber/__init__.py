"""Support for Tibber."""

from __future__ import annotations

from dataclasses import dataclass
import logging

import aiohttp
from aiohttp.client_exceptions import ClientError, ClientResponseError
import tibber
from tibber import data_api as tibber_data_api

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util, ssl as ssl_util

from .const import (
    API_TYPE_DATA_API,
    API_TYPE_GRAPHQL,
    CONF_API_TYPE,
    DATA_HASS_CONFIG,
    DOMAIN,
)
from .services import async_setup_services

GRAPHQL_PLATFORMS = [Platform.NOTIFY, Platform.SENSOR]
DATA_API_PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class TibberGraphQLRuntimeData:
    """Runtime data for GraphQL-based Tibber entries."""

    tibber: tibber.Tibber


@dataclass(slots=True)
class TibberDataAPIRuntimeData:
    """Runtime data for Tibber Data API entries."""

    session: OAuth2Session
    _client: tibber_data_api.TibberDataAPI | None = None

    async def async_get_client(
        self, hass: HomeAssistant
    ) -> tibber_data_api.TibberDataAPI:
        """Return an authenticated Tibber Data API client."""
        await self.session.async_ensure_token_valid()
        token = self.session.token
        access_token = token.get(CONF_ACCESS_TOKEN)
        if not access_token:
            raise ConfigEntryAuthFailed("Access token missing from OAuth session")
        if self._client is None:
            self._client = tibber_data_api.TibberDataAPI(
                access_token,
                websession=async_get_clientsession(hass),
            )
        self._client.set_access_token(access_token)
        return self._client


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tibber component."""

    hass.data[DATA_HASS_CONFIG] = config
    hass.data.setdefault(DOMAIN, {})

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""

    hass.data.setdefault(DOMAIN, {})
    api_type = entry.data.get(CONF_API_TYPE, API_TYPE_GRAPHQL)

    if api_type == API_TYPE_DATA_API:
        return await _async_setup_data_api_entry(hass, entry)

    return await _async_setup_graphql_entry(hass, entry)


async def _async_setup_graphql_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the legacy GraphQL Tibber entry."""

    tibber_connection = tibber.Tibber(
        access_token=entry.data[CONF_ACCESS_TOKEN],
        websession=async_get_clientsession(hass),
        time_zone=dt_util.get_default_time_zone(),
        ssl=ssl_util.get_default_context(),
    )

    runtime = TibberGraphQLRuntimeData(tibber_connection)
    entry.runtime_data = runtime
    hass.data[DOMAIN][API_TYPE_GRAPHQL] = runtime

    async def _close(_event: Event) -> None:
        await tibber_connection.rt_disconnect()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close))

    try:
        await tibber_connection.update_info()
    except (
        TimeoutError,
        aiohttp.ClientError,
        tibber.RetryableHttpExceptionError,
    ) as err:
        raise ConfigEntryNotReady("Unable to connect") from err
    except tibber.InvalidLoginError as err:
        _LOGGER.error("Failed to login to Tibber GraphQL API: %s", err)
        return False
    except tibber.FatalHttpExceptionError as err:
        _LOGGER.error("Fatal error communicating with Tibber GraphQL API: %s", err)
        return False

    await hass.config_entries.async_forward_entry_setups(entry, GRAPHQL_PLATFORMS)

    return True


async def _async_setup_data_api_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Tibber Data API entry."""

    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err

    session = OAuth2Session(hass, entry, implementation)

    try:
        await session.async_ensure_token_valid()
    except ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed(
                "OAuth session is not valid, reauthentication required"
            ) from err
        raise ConfigEntryNotReady from err
    except ClientError as err:
        raise ConfigEntryNotReady from err

    runtime = TibberDataAPIRuntimeData(session=session)
    entry.runtime_data = runtime
    hass.data[DOMAIN][API_TYPE_DATA_API] = runtime

    await hass.config_entries.async_forward_entry_setups(entry, DATA_API_PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    api_type = config_entry.data.get(CONF_API_TYPE, API_TYPE_GRAPHQL)
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry,
        GRAPHQL_PLATFORMS if api_type == API_TYPE_GRAPHQL else DATA_API_PLATFORMS,
    )

    if unload_ok:
        if api_type == API_TYPE_GRAPHQL:
            runtime = hass.data[DOMAIN].get(api_type)
            if runtime:
                tibber_connection = runtime.tibber
                await tibber_connection.rt_disconnect()

        hass.data[DOMAIN].pop(api_type, None)
    return unload_ok
