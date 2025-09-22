"""The Meteo.lt integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import MeteoLtApi, MeteoLtApiConnectionError
from .const import CONF_PLACE_CODE, DOMAIN
from .coordinator import MeteoLtUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.WEATHER]

type MeteoLtConfigEntry = ConfigEntry[MeteoLtUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MeteoLtConfigEntry) -> bool:
    """Set up Meteo.lt from a config entry."""
    place_code = entry.data[CONF_PLACE_CODE]

    api = MeteoLtApi(hass)
    coordinator = MeteoLtUpdateCoordinator(hass, api, place_code)

    try:
        await coordinator.async_config_entry_first_refresh()
    except MeteoLtApiConnectionError as err:
        raise ConfigEntryNotReady(f"Unable to connect to Meteo.lt API: {err}") from err

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MeteoLtConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
