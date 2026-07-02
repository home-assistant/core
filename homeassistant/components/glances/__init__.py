"""The Glances integration."""

import logging
from typing import Any

from glances_api import Glances
from glances_api.exceptions import (
    GlancesApiAuthorizationError,
    GlancesApiError,
    GlancesApiNoDataAvailable,
)
import httpx

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.httpx_client import create_async_httpx_client
from homeassistant.util.hass_dict import HassKey

from .const import DEFAULT_TIMEOUT
from .coordinator import GlancesConfigEntry, GlancesDataUpdateCoordinator

DATA_HTTPX_CLIENT: HassKey[dict[bool, httpx.AsyncClient]] = HassKey(
    "glances_httpx_client"
)

PLATFORMS = [Platform.SENSOR]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: GlancesConfigEntry
) -> bool:
    """Set up Glances from config entry."""
    try:
        api = await get_api(hass, dict(config_entry.data))
    except GlancesApiAuthorizationError as err:
        raise ConfigEntryAuthFailed from err
    except GlancesApiError as err:
        raise ConfigEntryNotReady from err
    except ServerVersionMismatch as err:
        raise ConfigEntryError(err) from err
    coordinator = GlancesDataUpdateCoordinator(hass, config_entry, api)
    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GlancesConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@callback
def _async_get_httpx_client(hass: HomeAssistant, verify_ssl: bool) -> httpx.AsyncClient:
    """Return a cached Glances httpx client (one per verify_ssl value).

    The shared httpx client cannot be used because it has a 5-second timeout
    that is too short for slow Glances hosts. Caching here ensures entry
    reloads reuse the same client instead of leaking one on every reload.
    """
    clients = hass.data.setdefault(DATA_HTTPX_CLIENT, {})
    if (client := clients.get(verify_ssl)) is None:
        client = clients[verify_ssl] = create_async_httpx_client(
            hass, verify_ssl=verify_ssl, timeout=DEFAULT_TIMEOUT
        )
    return client


async def get_api(hass: HomeAssistant, entry_data: dict[str, Any]) -> Glances:
    """Return the api from glances_api."""
    httpx_client = _async_get_httpx_client(hass, entry_data[CONF_VERIFY_SSL])
    for version in (4, 3):
        api = Glances(
            host=entry_data[CONF_HOST],
            port=entry_data[CONF_PORT],
            version=version,
            ssl=entry_data[CONF_SSL],
            username=entry_data.get(CONF_USERNAME),
            password=entry_data.get(CONF_PASSWORD),
            httpx_client=httpx_client,
        )
        try:
            await api.get_ha_sensor_data()
        except GlancesApiNoDataAvailable as err:
            _LOGGER.debug("Failed to connect to Glances API v%s: %s", version, err)
            continue
        _LOGGER.debug("Connected to Glances API v%s", version)
        return api
    raise ServerVersionMismatch("Could not connect to Glances API version 3 or 4")


class ServerVersionMismatch(HomeAssistantError):
    """Raise exception if we fail to connect to Glances API."""
