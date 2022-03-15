"""The decora_wifi component."""

import logging

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.LIGHT]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Decora WiFi."""

    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            data=config[DOMAIN],
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Decora WiFi entries."""

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


def trigger_import(hass: HomeAssistant, config: ConfigType) -> None:
    """Trigger an import of YAML config into a config_entry."""

    _LOGGER.warning(
        "Decora WiFi YAML configuration is deprecated; your YAML configuration "
        "has been imported into the UI and can be safely removed"
    )

    data = {}
    for key in (CONF_USERNAME, CONF_PASSWORD):
        if config.get(key):
            data[key] = config[key]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=data
        )
    )
