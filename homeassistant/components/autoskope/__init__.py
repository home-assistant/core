"""The Autoskope integration."""

from __future__ import annotations

import logging

from autoskope_client.api import AutoskopeApi
from autoskope_client.models import CannotConnect, InvalidAuth
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_HOST
from .coordinator import (
    AutoskopeConfigEntry,
    AutoskopeDataUpdateCoordinator,
    AutoskopeRuntimeData,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: AutoskopeConfigEntry) -> bool:
    """Set up Autoskope from a config entry."""

    api = AutoskopeApi(
        host=entry.data.get(CONF_HOST, DEFAULT_HOST),
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    try:
        if not await api.authenticate(session=async_get_clientsession(hass)):
            _LOGGER.error("Authentication failed unexpectedly during setup")
            return False
    except InvalidAuth:
        _LOGGER.warning(
            "Authentication failed for Autoskope entry %s. Please re-authenticate",
            entry.entry_id,
        )
        return False
    except CannotConnect as err:
        _LOGGER.warning("Could not connect to Autoskope API")
        raise ConfigEntryNotReady("Could not connect to Autoskope API") from err
    except Exception:
        _LOGGER.exception(
            "Unexpected error setting up Autoskope entry %s", entry.entry_id
        )
        return False

    coordinator = AutoskopeDataUpdateCoordinator(hass, api=api, entry=entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AutoskopeRuntimeData(coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AutoskopeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
