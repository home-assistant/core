"""The apprise component."""

import apprise

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_NAME, DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
type AppriseConfigEntry = ConfigEntry[apprise.AppriseConfig]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Apprise component from YAML config."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Apprise from a config entry."""

    conf = entry.data
    name = conf.get("name", DEFAULT_NAME)
    config = conf.get("config")
    url = conf.get("url")

    apprise_config = apprise.AppriseConfig(name=name, config=config, url=url)
    entry.runtime_data = apprise_config

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Apprise config entry."""
    return True
