"""The GridX integration."""

from __future__ import annotations

import httpx

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.httpx_client import create_async_httpx_client

from .client import async_create_connector, load_oem_config
from .const import CONF_OEM, DOMAIN, LOGGER
from .coordinator import GridxHistoricalCoordinator, GridxLiveCoordinator
from .types import GridxConfigEntry, GridxData

PLATFORMS = [Platform.SENSOR]
API_BASE_URL = "https://api.gridx.de"


async def async_setup_entry(hass: HomeAssistant, entry: GridxConfigEntry) -> bool:
    """Set up GridX from a config entry."""
    username: str = entry.data[CONF_USERNAME]
    password: str = entry.data[CONF_PASSWORD]
    oem: str = entry.data[CONF_OEM]

    config = load_oem_config(oem, username, password)
    httpx_client = create_async_httpx_client(
        hass,
        auto_cleanup=False,
        base_url=API_BASE_URL,
    )

    try:
        connector = await async_create_connector(config, httpx_client)
    except PermissionError as err:
        await httpx_client.aclose()
        LOGGER.error("GridX authentication failed: %s", err)
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except httpx.HTTPStatusError as err:
        await httpx_client.aclose()
        status = err.response.status_code if err.response else None
        LOGGER.error("Error connecting to GridX: %s", err)
        if status in (401, 403):
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except httpx.HTTPError as err:
        await httpx_client.aclose()
        LOGGER.error("Error connecting to GridX: %s", err)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except (RuntimeError, TypeError, ValueError) as err:
        await httpx_client.aclose()
        LOGGER.error("Error connecting to GridX: %s", err)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    live_coordinator = GridxLiveCoordinator(hass, entry, connector)
    hist_coordinator = GridxHistoricalCoordinator(hass, entry, connector)

    await live_coordinator.async_config_entry_first_refresh()
    await hist_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = GridxData(
        connector=connector,
        live_coordinator=live_coordinator,
        hist_coordinator=hist_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GridxConfigEntry) -> bool:
    """Unload a GridX config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.connector.close()
    return unload_ok
