"""Duck DNS integration."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import DuckDnsConfigEntry, DuckDnsUpdateCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the DuckDNS component."""

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: DuckDnsConfigEntry) -> bool:
    """Set up Duck DNS from a config entry."""

    coordinator = DuckDnsUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Add a dummy listener as we do not have regular entities
    entry.async_on_unload(coordinator.async_add_listener(lambda: None))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DuckDnsConfigEntry) -> bool:
    """Unload a config entry."""
    return True
