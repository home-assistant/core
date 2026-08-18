"""The surepetcare integration."""

from datetime import timedelta
import logging

from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import SurePetcareConfigEntry, SurePetcareDataCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.LOCK, Platform.SENSOR]
SCAN_INTERVAL = timedelta(minutes=3)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Sure Petcare services."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SurePetcareConfigEntry) -> bool:
    """Set up Sure Petcare from a config entry."""
    try:
        coordinator = SurePetcareDataCoordinator(hass, entry)
    except SurePetcareAuthenticationError as error:
        _LOGGER.error("Unable to connect to surepetcare.io: Wrong credentials!")
        raise ConfigEntryAuthFailed from error
    except SurePetcareError as error:
        raise ConfigEntryNotReady from error

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SurePetcareConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
