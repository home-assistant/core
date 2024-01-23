"""The sql component."""
from __future__ import annotations

import logging

import sqlparse
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
    CONF_ICON,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.trigger_template_entity import (
    CONF_AVAILABILITY,
    CONF_PICTURE,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_COLUMN_NAME, CONF_QUERY, DOMAIN, PLATFORMS
from .util import redact_credentials

_LOGGER = logging.getLogger(__name__)


def validate_sql_select(value: str) -> str:
    """Validate that value is a SQL SELECT query."""
    if len(query := sqlparse.parse(value.lstrip().lstrip(";"))) > 1:
        raise vol.Invalid("Multiple SQL queries are not supported")
    if len(query) == 0 or (query_type := query[0].get_type()) == "UNKNOWN":
        raise vol.Invalid("Invalid SQL query")
    if query_type != "SELECT":
        _LOGGER.debug("The SQL query %s is of type %s", query, query_type)
        raise vol.Invalid("Only SELECT queries allowed")
    return str(query[0])


QUERY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COLUMN_NAME): cv.string,
        vol.Required(CONF_NAME): cv.template,
        vol.Required(CONF_QUERY): vol.All(cv.string, validate_sql_select),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_DB_URL): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_STATE_CLASS): STATE_CLASSES_SCHEMA,
        vol.Optional(CONF_AVAILABILITY): cv.template,
        vol.Optional(CONF_ICON): cv.template,
        vol.Optional(CONF_PICTURE): cv.template,
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
    _LOGGER.debug(
        "Comparing %s and %s",
        redact_credentials(entry.options.get(CONF_DB_URL)),
        redact_credentials(get_instance(hass).db_url),
    )
    if entry.options.get(CONF_DB_URL) == get_instance(hass).db_url:
        remove_configured_db_url_if_not_needed(hass, entry)

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload SQL config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
