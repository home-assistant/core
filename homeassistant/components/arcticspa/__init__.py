"""The Arctic Spa integration."""
from __future__ import annotations

import logging

from pyarcticspas import Spa
from pyarcticspas.error import SpaHTTPException, TooManyRequestsError, UnauthorizedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import ArcticSpaDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an Arctic Spa from a config entry."""

    device = Spa(entry.data[CONF_API_KEY])

    # The API has no login endpoint. We will use a status check to test access and availability.
    try:
        await device.async_status()
    except UnauthorizedError as ex:
        raise ConfigEntryError("Invalid API token") from ex
    except TooManyRequestsError as ex:
        raise ConfigEntryNotReady("API overloaded, please try later") from ex
    except SpaHTTPException as ex:
        raise ConfigEntryNotReady(f"API returned {ex.code} {ex.msg}") from ex

    data_update_coordinator = ArcticSpaDataUpdateCoordinator(hass, device)
    await data_update_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data_update_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
