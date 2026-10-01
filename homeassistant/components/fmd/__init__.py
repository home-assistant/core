"""The FMD integration for Home Assistant.

Home Assistant integration for FMD (Find My Device).
Built to work with the FMD-FOSS project: https://fmd-foss.org

FMD Project Attribution:
- Created by Nulide (http://nulide.de)
- Maintained by Thore (https://thore.io) and the FMD-FOSS team
- FMD Android: https://gitlab.com/fmd-foss/fmd-android
- FMD Server: https://gitlab.com/fmd-foss/fmd-server

This integration:
- MIT License - Copyright (c) 2025 Devin Slick
- https://github.com/devinslick/home-assistant-fmd
- A third-party client for FMD servers
"""

import logging

from fmd_api import AuthenticationError, FmdApiException, FmdClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN  # noqa: F401
from .coordinator import FmdCoordinator

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]

_LOGGER = logging.getLogger(__name__)


type FmdConfigEntry = ConfigEntry[FmdCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: FmdConfigEntry) -> bool:
    """Set up FMD from a config entry."""
    try:
        api = await FmdClient.from_auth_artifacts(entry.data["artifacts"])
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except FmdApiException as err:
        raise ConfigEntryNotReady(f"FMD API error during setup: {err}") from err

    coordinator = FmdCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FmdConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.api.close()
    return unload_ok
