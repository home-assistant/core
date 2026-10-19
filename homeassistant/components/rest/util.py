"""Helpers for RESTful API."""

import asyncio
from collections.abc import Coroutine
from datetime import timedelta
import logging
from typing import Any

import aiohttp
from jsonpath import ExprSyntaxError, JSONPathTypeError, search

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_PARAMS,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_RESOURCE,
    CONF_RESOURCE_TEMPLATE,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import discovery, template
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.async_ import create_eager_task
from homeassistant.util.json import json_loads

from .const import (
    CONF_ENCODING,
    CONF_PAYLOAD_TEMPLATE,
    CONF_SSL_CIPHER_LIST,
    COORDINATOR,
    DEFAULT_SSL_CIPHER_LIST,
    DOMAIN,
    PLATFORM_IDX,
    REST_IDX,
)
from .coordinator import RestCoordinator
from .data import RestData

_LOGGER = logging.getLogger(__name__)


def parse_json_attributes(
    value: str | None, json_attrs: list[str], json_attrs_path: str | None
) -> dict[str, Any]:
    """Parse JSON attributes."""
    if not value:
        _LOGGER.warning("Empty reply found when expecting JSON data")
        return {}

    try:
        json_dict = json_loads(value)
        if json_attrs_path is not None:
            json_dict = search(json_attrs_path, json_dict)
        if isinstance(json_dict, list) and json_dict:
            json_dict = json_dict[0]
        if isinstance(json_dict, dict):
            return {k: json_dict[k] for k in json_attrs if k in json_dict}

        _LOGGER.warning(
            "JSON result was not a dictionary or list with 0th element a dictionary"
        )
    except ValueError, TypeError, ExprSyntaxError, JSONPathTypeError:
        _LOGGER.warning("REST result could not be parsed as JSON")
        _LOGGER.debug("Erroneous JSON: %s", value)

    return {}


COORDINATOR_AWARE_PLATFORMS = [SENSOR_DOMAIN, BINARY_SENSOR_DOMAIN]


@callback
def async_setup_shared_data(hass: HomeAssistant) -> None:
    """Create shared data for platform config and rest coordinators."""
    hass.data[DOMAIN] = {key: [] for key in (COORDINATOR, *COORDINATOR_AWARE_PLATFORMS)}


async def async_process_config(hass: HomeAssistant, config: ConfigType) -> bool:
    """Process rest configuration."""
    if DOMAIN not in config:
        return True

    refresh_coroutines: list[Coroutine[Any, Any, None]] = []
    load_coroutines: list[Coroutine[Any, Any, None]] = []
    rest_config: list[ConfigType] = config[DOMAIN]
    for rest_idx, conf in enumerate(rest_config):
        scan_interval: timedelta = conf.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        resource_template: template.Template | None = conf.get(CONF_RESOURCE_TEMPLATE)
        payload_template: template.Template | None = conf.get(CONF_PAYLOAD_TEMPLATE)
        rest = create_rest_data_from_config(hass, conf)
        coordinator = RestCoordinator(
            hass, rest, None, resource_template, payload_template, scan_interval
        )
        refresh_coroutines.append(coordinator.async_refresh())
        hass.data[DOMAIN][COORDINATOR].append(coordinator)

        for platform_domain in COORDINATOR_AWARE_PLATFORMS:
            if platform_domain not in conf:
                continue

            for platform_conf in conf[platform_domain]:
                hass.data[DOMAIN][platform_domain].append(platform_conf)
                platform_idx = len(hass.data[DOMAIN][platform_domain]) - 1

                load_coroutine = discovery.async_load_platform(
                    hass,
                    platform_domain,
                    DOMAIN,
                    {REST_IDX: rest_idx, PLATFORM_IDX: platform_idx},
                    config,
                )
                load_coroutines.append(load_coroutine)

    if refresh_coroutines:
        await asyncio.gather(*(create_eager_task(coro) for coro in refresh_coroutines))

    if load_coroutines:
        await asyncio.gather(*(create_eager_task(coro) for coro in load_coroutines))

    return True


def create_rest_data_from_config(hass: HomeAssistant, config: ConfigType) -> RestData:
    """Create RestData from config."""
    resource: str | None = config.get(CONF_RESOURCE)
    resource_template: template.Template | None = config.get(CONF_RESOURCE_TEMPLATE)
    method: str = config[CONF_METHOD]
    payload: str | None = config.get(CONF_PAYLOAD)
    payload_template: template.Template | None = config.get(CONF_PAYLOAD_TEMPLATE)
    verify_ssl: bool = config[CONF_VERIFY_SSL]
    ssl_cipher_list: str = config.get(CONF_SSL_CIPHER_LIST, DEFAULT_SSL_CIPHER_LIST)
    username: str | None = config.get(CONF_USERNAME)
    password: str | None = config.get(CONF_PASSWORD)
    headers: dict[str, str] | None = config.get(CONF_HEADERS)
    params: dict[str, str] | None = config.get(CONF_PARAMS)
    timeout: int = config[CONF_TIMEOUT]
    encoding: str = config[CONF_ENCODING]
    if resource_template is not None:
        resource = resource_template.async_render(parse_result=False)

    if payload_template is not None:
        payload = payload_template.async_render(parse_result=False)

    if not resource:
        raise HomeAssistantError("Resource not set for RestData")

    auth: aiohttp.DigestAuthMiddleware | tuple[str, str] | None = None
    if username and password:
        if config.get(CONF_AUTHENTICATION) == HTTP_DIGEST_AUTHENTICATION:
            auth = aiohttp.DigestAuthMiddleware(username, password)
        else:
            auth = (username, password)

    return RestData(
        hass,
        method,
        resource,
        encoding,
        auth,
        headers,
        params,
        payload,
        verify_ssl,
        ssl_cipher_list,
        timeout,
    )
