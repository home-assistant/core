"""Support for Obihai Sensors."""
from __future__ import annotations

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DEFAULT_PASSWORD, DEFAULT_USERNAME, DOMAIN, LOGGER
from .obihai_api import ObihaiConnection

SCAN_INTERVAL = timedelta(seconds=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    }
)


# DEPRECATED
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Obihai sensor platform."""
    LOGGER.warning(
        "Configuration of the Obihai platform in YAML is deprecated "
        "and will be removed in Home Assistant 2023.6; Your existing "
        "configuration has been imported into the UI automatically and can be "
        "safely removed from your configuration.yaml file"
    )

    if discovery_info:
        config = PLATFORM_SCHEMA(discovery_info)

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Obihai sensor entries."""

    username = entry.options[CONF_USERNAME]
    password = entry.options[CONF_PASSWORD]
    host = entry.options[CONF_HOST]
    requester = ObihaiConnection(host, username, password)

    await hass.async_add_executor_job(requester.update)
    sensors = requester.sensors

    async_add_entities(sensors, update_before_add=True)
