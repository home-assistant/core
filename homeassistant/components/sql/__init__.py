"""The sql component."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.recorder import CONF_DB_URL, get_instance
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA,
    STATE_CLASSES_SCHEMA,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_COLUMN_NAME, CONF_QUERY, DOMAIN, PLATFORMS


def validate_sql_select(value: str) -> str:
    """Validate that value is a SQL SELECT query."""
    if not value.lstrip().lower().startswith("select"):
        raise vol.Invalid("Only SELECT queries allowed")
    return value


QUERY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COLUMN_NAME): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_QUERY): vol.All(cv.string, validate_sql_select),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_DB_URL): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_STATE_CLASS): STATE_CLASSES_SCHEMA,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): vol.All(cv.ensure_list, [QUERY_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)


def remove_configured_db_url_if_not_needed(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove db url from config if it matches recorder database."""
    hass.config_entries.async_update_entry(
        entry,
        options={
            key: value for key, value in entry.options.items() if key != CONF_DB_URL
        },
    )


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener for options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up SQL from yaml config."""
    if (conf := config.get(DOMAIN)) is None:
        return True

    for sensor_conf in conf:
        await discovery.async_load_platform(
            hass, Platform.SENSOR, DOMAIN, sensor_conf, config
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SQL from a config entry."""
    if entry.options.get(CONF_DB_URL) == get_instance(hass).db_url:
        remove_configured_db_url_if_not_needed(hass, entry)

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload SQL config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
