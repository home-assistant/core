"""Integrate with DuckDNS."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import DuckDnsConfigEntry, DuckDnsUpdateCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_DOMAIN): cv.string,
                vol.Required(CONF_ACCESS_TOKEN): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the DuckDNS component."""

    async_setup_services(hass)

    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
        )
    )

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
