"""The apprise component."""

import apprise

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_NAME, DOMAIN

type AppriseConfigEntry = ConfigEntry[apprise.AppriseConfig]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Apprise component from YAML config."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config[DOMAIN],
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: AppriseConfigEntry) -> bool:
    """Set up Apprise from a config entry."""

    conf = entry.data
    name = conf.get(CONF_NAME, DEFAULT_NAME)
    config = conf.get("config")
    url = conf.get(CONF_URL)

    apprise_config = apprise.AppriseConfig(name=name, config=config, url=url)
    entry.runtime_data = apprise_config

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AppriseConfigEntry) -> bool:
    """Unload a Apprise config entry."""
    return True
