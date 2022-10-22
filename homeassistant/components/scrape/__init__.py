"""The scrape component."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import httpx
import voluptuous as vol

from homeassistant.components.rest.data import RestData
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA,
    STATE_CLASSES_SCHEMA,
)
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
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_INDEX, CONF_SELECT, DEFAULT_NAME, DEFAULT_VERIFY_SSL, DOMAIN
from .coordinator import ScrapeCoordinator

_LOGGER = logging.getLogger(__name__)

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
        vol.Optional(CONF_SCAN_INTERVAL): cv.positive_int,
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

    hass.data[DOMAIN] = {}

    sensor_conf: dict[str, Any]
    for sensor_id, sensor_conf in enumerate(conf):
        resource: str = sensor_conf[CONF_RESOURCE]
        method: str = "GET"
        payload: str | None = None
        headers: dict[str, str] | None = sensor_conf.get(CONF_HEADERS)
        verify_ssl: bool = sensor_conf[CONF_VERIFY_SSL]
        username: str | None = sensor_conf.get(CONF_USERNAME)
        password: str | None = sensor_conf.get(CONF_PASSWORD)
        authentication = sensor_conf.get(CONF_AUTHENTICATION)
        update_interval = sensor_conf.get(CONF_SCAN_INTERVAL, 10 * 60)
        auth: httpx.DigestAuth | tuple[str, str] | None = None
        if username and password:
            if authentication == HTTP_DIGEST_AUTHENTICATION:
                auth = httpx.DigestAuth(username, password)
            else:
                auth = (username, password)

        rest = RestData(
            hass, method, resource, auth, headers, None, payload, verify_ssl
        )

        get_coordinator: ScrapeCoordinator
        new_coordinator = None
        for get_coordinator in hass.data[DOMAIN].values():
            if rest == get_coordinator.rest:
                new_coordinator = get_coordinator
        hass.data[DOMAIN][sensor_id] = (
            new_coordinator
            if new_coordinator
            else await create_coordinator(hass, rest, update_interval)
        )

        discovery.load_platform(
            hass,
            Platform.SENSOR,
            DOMAIN,
            {"id": sensor_id, "config": sensor_conf},
            config,
        )

    return True


async def create_coordinator(
    hass: HomeAssistant, rest: RestData, update_interval: int
) -> ScrapeCoordinator:
    """Get Scrape Coordinator."""

    coordinator = ScrapeCoordinator(hass, rest, timedelta(seconds=update_interval))
    await coordinator.async_refresh()
    if coordinator.data is None:
        raise PlatformNotReady
    return coordinator
