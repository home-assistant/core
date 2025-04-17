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
from homeassistant.const import CONF_API_KEY, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import PortainerCoordinator
from .models import PortainerData

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]

type PortainerConfigEntry = ConfigEntry[PortainerData]


async def async_setup_entry(hass: HomeAssistant, entry: PortainerConfigEntry) -> bool:
    """Set up Portainer from a config entry."""

    _LOGGER.debug("Setting up Portainer API: %s", entry.data[CONF_URL])

    client = Portainer(
        api_url=entry.data[CONF_URL],
        api_key=entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )

    try:
        endpoints = await client.get_endpoints()
    except PortainerAuthenticationError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except PortainerConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except PortainerTimeoutError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="timeout_connect",
        ) from err

    _LOGGER.debug("Connected to Portainer API: %s", entry.data[CONF_URL])

    assert endpoints

    coordinator = PortainerCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = PortainerData(coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PortainerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
