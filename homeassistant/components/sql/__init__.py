"""The sql component."""

from __future__ import annotations

import logging
from typing import Any

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
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.trigger_template_entity import (
    CONF_AVAILABILITY,
    CONF_PICTURE,
    ValueTemplate,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ADVANCED_OPTIONS,
    CONF_COLUMN_NAME,
    CONF_QUERY,
    DOMAIN,
    PLATFORMS,
)
from .services import async_setup_services
from .util import redact_credentials, validate_sql_select

_LOGGER = logging.getLogger(__name__)


QUERY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COLUMN_NAME): cv.string,
        vol.Required(CONF_NAME): cv.template,
        vol.Required(CONF_QUERY): vol.All(cv.string, validate_sql_select),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): vol.All(
            cv.template, ValueTemplate.from_template
        ),
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up SQL from yaml config."""
    async_setup_services(hass)

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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload SQL config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s.%s", entry.version, entry.minor_version)

    if entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if entry.version == 1:
        old_options = {**entry.options}
        new_data = {}
        new_options: dict[str, Any] = {}

        if (db_url := old_options.get(CONF_DB_URL)) and db_url != get_instance(
            hass
        ).db_url:
            new_data[CONF_DB_URL] = db_url

        new_options[CONF_COLUMN_NAME] = old_options.get(CONF_COLUMN_NAME)
        new_options[CONF_QUERY] = old_options.get(CONF_QUERY)
        new_options[CONF_ADVANCED_OPTIONS] = {}

        for key in (
            CONF_VALUE_TEMPLATE,
            CONF_UNIT_OF_MEASUREMENT,
            CONF_DEVICE_CLASS,
            CONF_STATE_CLASS,
        ):
            if (value := old_options.get(key)) is not None:
                new_options[CONF_ADVANCED_OPTIONS][key] = value

        hass.config_entries.async_update_entry(
            entry, data=new_data, options=new_options, version=2
        )

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        entry.version,
        entry.minor_version,
    )

    return True
