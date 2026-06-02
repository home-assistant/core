"""The Noonlight emergency-dispatch integration."""

import logging

from noonlight_dispatch import (
    NoonlightAuthError,
    NoonlightConnectionError,
    NoonlightResponseError,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, HEARTBEAT_PROBE_ID, PLATFORMS
from .coordinator import NoonlightConfigEntry, NoonlightCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Noonlight integration.

    Domain-level services are registered here so they exist even when no
    config entry is loaded; the handlers resolve the target entry at call time.
    """
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: NoonlightConfigEntry) -> bool:
    """Set up a Noonlight config entry."""
    coordinator = NoonlightCoordinator(hass, entry)
    await coordinator.async_load()
    # Establish initial data; the first refresh is a no-op while idle.
    await coordinator.async_config_entry_first_refresh()

    # Confirm Noonlight is reachable and the token is accepted before we
    # advertise entities. A GET against a bogus alarm id has no side effects:
    # a 404 means reachable+authed, 401 means the token is bad, and a
    # transport error means Noonlight is unreachable (retry later).
    try:
        await coordinator.api.get_alarm_status(HEARTBEAT_PROBE_ID)
    except NoonlightAuthError as err:
        raise ConfigEntryAuthFailed("Noonlight rejected the API token") from err
    except NoonlightConnectionError as err:
        raise ConfigEntryNotReady("Cannot reach Noonlight") from err
    except NoonlightResponseError as err:
        if err.status_code != 404:
            raise ConfigEntryNotReady(
                "Noonlight returned an unexpected response"
            ) from err

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NoonlightConfigEntry) -> bool:
    """Unload a Noonlight config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False

    await entry.runtime_data.async_shutdown()
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: NoonlightConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
