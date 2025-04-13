"""The Portainer integration."""

from __future__ import annotations

import logging

from pyportainer import (
    Portainer,
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import PortainerCoordinator
from .models import PortainerData

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [Platform.SENSOR]

type PortainerConfigEntry = ConfigEntry[PortainerData]


async def async_setup_entry(hass: HomeAssistant, entry: PortainerConfigEntry) -> bool:
    """Set up Portainer from a config entry."""
    if CONF_API_KEY not in entry.data:
        raise ConfigEntryAuthFailed

    _LOGGER.debug("Setting up Portainer API: %s", entry.data[CONF_HOST])

    api_url = f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"

    client = Portainer(
        api_url=api_url,
        api_key=entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )

    try:
        endpoints = await client.get_endpoints()
    except PortainerAuthenticationError as err:
        raise ConfigEntryError(
            f"Invalid Portainer authentication. Error: {err}"
        ) from err
    except PortainerConnectionError as err:
        raise ConfigEntryNotReady(f"Error during Portainer setup: {err}") from err
    except PortainerTimeoutError as err:
        raise ConfigEntryNotReady(f"Timeout during Portainer setup: {err}") from err

    _LOGGER.debug("Connected to Portainer API: %s", api_url)

    assert endpoints

    coordinator = PortainerCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = PortainerData(coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PortainerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
