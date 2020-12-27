"""Support for tracking the proximity of a device."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICES, CONF_UNIT_OF_MEASUREMENT, CONF_ZONE
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    CONF_IGNORED_ZONES,
    CONF_TOLERANCE,
    DEFAULT_PROXIMITY_ZONE,
    DEFAULT_TOLERANCE,
    DOMAIN,
    UNITS,
)

_LOGGER = logging.getLogger(__name__)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ZONE, default=DEFAULT_PROXIMITY_ZONE): cv.string,
        vol.Optional(CONF_DEVICES, default=[]): vol.All(cv.ensure_list, [cv.entity_id]),
        vol.Optional(CONF_IGNORED_ZONES, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_TOLERANCE, default=DEFAULT_TOLERANCE): cv.positive_int,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): vol.All(cv.string, vol.In(UNITS)),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: cv.schema_with_slug_keys(ZONE_SCHEMA)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the proximity environment."""
    hass.data.setdefault(DOMAIN, {})

    if config.get(DOMAIN) is None:
        return True

    for conf in config[DOMAIN].values():
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=conf,
            )
        )

    return True


async def async_setup_entry(
    hass: HomeAssistantType, entry: config_entries.ConfigEntry
) -> bool:
    """Set the config entry up."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True


async def async_unload_entry(
    hass: HomeAssistantType, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
