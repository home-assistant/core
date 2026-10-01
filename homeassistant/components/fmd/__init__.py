"""The FMD integration for Home Assistant.

Home Assistant integration for FMD (Find My Device).
Built to work with the FMD-FOSS project: https://fmd-foss.org

FMD Project Attribution:
- Created by Nulide (http://nulide.de)
- Maintained by Thore (https://thore.io) and the FMD-FOSS team
- FMD Android: https://gitlab.com/fmd-foss/fmd-android
- FMD Server: https://gitlab.com/fmd-foss/fmd-server

Client library: https://github.com/devinslick/fmd_api
"""

import logging

from fmd_api import AuthenticationError, FmdApiException, FmdClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import FmdCoordinator

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]

_LOGGER = logging.getLogger(__name__)


type FmdConfigEntry = ConfigEntry[FmdCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: FmdConfigEntry) -> bool:
    """Set up FMD from a config entry."""
    try:
        api = await FmdClient.from_auth_artifacts(entry.data["artifacts"])
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="setup_auth_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    except FmdApiException as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_not_ready",
            translation_placeholders={"error": str(err)},
        ) from err

    entry.async_on_unload(api.close)
    coordinator = FmdCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FmdConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
