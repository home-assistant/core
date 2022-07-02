"""The scrape component."""
from __future__ import annotations

from datetime import timedelta

import httpx
import voluptuous as vol

from homeassistant.components.rest.data import RestData
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA,
    STATE_CLASSES_SCHEMA,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_AUTHENTICATION,
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RESOURCE,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_INDEX,
    CONF_SELECT,
    DEFAULT_NAME,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PLATFORMS,
)

time_period = vol.Any(
    cv.time_period_str, cv.time_period_seconds, timedelta, cv.time_period_dict
)

SCRAPE_CONFIG = vol.Schema(
    {
        vol.Required(CONF_RESOURCE): cv.string,
        vol.Required(CONF_SELECT): cv.string,
        vol.Optional(CONF_ATTRIBUTE): cv.string,
        vol.Optional(CONF_INDEX, default=0): cv.positive_int,
        vol.Optional(CONF_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Optional(CONF_HEADERS): vol.Schema({cv.string: cv.string}),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_STATE_CLASS): STATE_CLASSES_SCHEMA,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL): time_period,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): vol.All(cv.ensure_list, [SCRAPE_CONFIG])},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Scrape from yaml config."""
    if (conf := config.get(DOMAIN)) is None:
        return True

    for sensor_conf in conf:
        discovery.load_platform(hass, "sensor", DOMAIN, sensor_conf, config)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Scrape from a config entry."""

    resource: str = entry.options[CONF_RESOURCE]
    method: str = "GET"
    payload: str | None = None
    headers: str | None = entry.options.get(CONF_HEADERS)
    verify_ssl: bool = entry.options[CONF_VERIFY_SSL]
    username: str | None = entry.options.get(CONF_USERNAME)
    password: str | None = entry.options.get(CONF_PASSWORD)
    authentication = entry.options.get(CONF_AUTHENTICATION)

    rest = await load_rest_data(
        hass,
        resource,
        method,
        payload,
        headers,
        verify_ssl,
        username,
        password,
        authentication,
    )

    if rest.data is None:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = rest

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def load_rest_data(
    hass: HomeAssistant,
    resource: str,
    method: str,
    payload: str | None,
    headers: str | None,
    verify_ssl: bool,
    username: str | None,
    password: str | None,
    authentication: str | None,
) -> RestData:
    """Load rest data."""

    auth: httpx.DigestAuth | tuple[str, str] | None = None
    if username and password:
        if authentication == HTTP_DIGEST_AUTHENTICATION:
            auth = httpx.DigestAuth(username, password)
        else:
            auth = (username, password)

    rest = RestData(hass, method, resource, auth, headers, None, payload, verify_ssl)
    await rest.async_update()

    return rest


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener for options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Scrape config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
