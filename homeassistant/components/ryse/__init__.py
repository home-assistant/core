"""The RYSE integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ryse"

# Define CONFIG_SCHEMA for hassfest
CONFIG_SCHEMA = cv.config_entry_only_config_schema


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the RYSE component."""
    _LOGGER.debug("Setting up RYSE Device integration")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RYSE from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry

    await hass.config_entries.async_forward_entry_setups(entry, ["cover"])

    return True
