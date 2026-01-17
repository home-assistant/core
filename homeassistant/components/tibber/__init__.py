"""Support for Tibber."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

import aiohttp
from aiohttp.client_exceptions import ClientError, ClientResponseError
import tibber
from tibber import data_api as tibber_data_api

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
    AUTH_IMPLEMENTATION,
    CONF_LEGACY_ACCESS_TOKEN,
    DATA_HASS_CONFIG,
    DOMAIN,
    TibberConfigEntry,
)
from .coordinator import TibberDataAPICoordinator
from .services import async_setup_services

PLATFORMS = [Platform.BINARY_SENSOR, Platform.NOTIFY, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


@dataclass
class TibberRuntimeData:
    """Runtime data for Tibber API entries."""

    tibber_connection: tibber.Tibber
    session: OAuth2Session
    data_api_coordinator: TibberDataAPICoordinator | None = field(default=None)
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

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: TibberConfigEntry) -> bool:
    """Set up a config entry."""

    # Added in 2026.1 to migrate existing users to OAuth2 (Tibber Data API).
    # Can be removed after 2026.7
    if AUTH_IMPLEMENTATION not in entry.data:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="data_api_reauth_required",
        )

    tibber_connection = tibber.Tibber(
        access_token=entry.data[CONF_LEGACY_ACCESS_TOKEN],
        websession=async_get_clientsession(hass),
        time_zone=dt_util.get_default_time_zone(),
        ssl=ssl_util.get_default_context(),
    )

    async def _close(event: Event) -> None:
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
    except tibber.InvalidLoginError as exp:
        _LOGGER.error("Failed to login. %s", exp)
        return False
    except tibber.FatalHttpExceptionError:
        return False

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

    entry.runtime_data = TibberRuntimeData(
        tibber_connection=tibber_connection,
        session=session,
    )

    coordinator = TibberDataAPICoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data.data_api_coordinator = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: TibberConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        await config_entry.runtime_data.tibber_connection.rt_disconnect()
    return unload_ok
