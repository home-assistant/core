"""The min_max component."""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_TYPE, CONF_UNIQUE_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ENTITY_IDS, CONF_ROUND_DIGITS, DOMAIN, PLATFORMS
from .sensor import ATTR_MAX_VALUE, SENSOR_TYPES

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_TYPE, default=SENSOR_TYPES[ATTR_MAX_VALUE]): vol.All(
            cv.string, vol.In(SENSOR_TYPES.values())
        ),
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_ENTITY_IDS): cv.entity_ids,
        vol.Optional(CONF_ROUND_DIGITS, default=2): vol.Coerce(int),
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): vol.All(cv.ensure_list, [SENSOR_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Min/Max from yaml config."""
    sensor_configs: list[ConfigType] | None
    if not (sensor_configs := config.get(DOMAIN)):
        return True

    load_coroutines: list[Coroutine[Any, Any, None]] = []
    for sensor_config in sensor_configs:
        load_coroutines.append(
            discovery.async_load_platform(
                hass,
                Platform.SENSOR,
                DOMAIN,
                sensor_config,
                config,
            )
        )

    if load_coroutines:
        await asyncio.gather(*load_coroutines)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Min/Max from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))

    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
