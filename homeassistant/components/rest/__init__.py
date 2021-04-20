"""The rest component."""

import asyncio
import logging

import httpx
import voluptuous as vol

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
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery
from homeassistant.helpers.entity_component import (
    DEFAULT_SCAN_INTERVAL,
    EntityComponent,
)
from homeassistant.helpers.reload import async_reload_integration_platforms
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import COORDINATOR, DOMAIN, PLATFORM_IDX, REST, REST_DATA, REST_IDX
from .data import RestData
from .schema import CONFIG_SCHEMA  # noqa: F401

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "notify", "sensor", "switch"]
COORDINATOR_AWARE_PLATFORMS = [SENSOR_DOMAIN, BINARY_SENSOR_DOMAIN]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the rest platforms."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    _async_setup_shared_data(hass)

    async def reload_service_handler(service):
        """Remove all user-defined groups and load new ones from config."""
        conf = await component.async_prepare_reload()
        if conf is None:
            return
        await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)
        _async_setup_shared_data(hass)
        await _async_process_config(hass, conf)

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=vol.Schema({})
    )

    return await _async_process_config(hass, config)


@callback
def _async_setup_shared_data(hass: HomeAssistant):
    """Create shared data for platform config and rest coordinators."""
    hass.data[DOMAIN] = {key: [] for key in [REST_DATA, *COORDINATOR_AWARE_PLATFORMS]}


async def _async_process_config(hass, config) -> bool:
    """Process rest configuration."""
    if DOMAIN not in config:
        return True

    refresh_tasks = []
    load_tasks = []
    for rest_idx, conf in enumerate(config[DOMAIN]):
        scan_interval = conf.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        resource_template = conf.get(CONF_RESOURCE_TEMPLATE)
        rest = create_rest_data_from_config(hass, conf)
        coordinator = _rest_coordinator(hass, rest, resource_template, scan_interval)
        refresh_tasks.append(coordinator.async_refresh())
        hass.data[DOMAIN][REST_DATA].append({REST: rest, COORDINATOR: coordinator})

        for platform_domain in COORDINATOR_AWARE_PLATFORMS:
            if platform_domain not in conf:
                continue

            for platform_conf in conf[platform_domain]:
                hass.data[DOMAIN][platform_domain].append(platform_conf)
                platform_idx = len(hass.data[DOMAIN][platform_domain]) - 1

                load = discovery.async_load_platform(
                    hass,
                    platform_domain,
                    DOMAIN,
                    {REST_IDX: rest_idx, PLATFORM_IDX: platform_idx},
                    config,
                )
                load_tasks.append(load)

    if refresh_tasks:
        await asyncio.gather(*refresh_tasks)

    if load_tasks:
        await asyncio.gather(*load_tasks)

    return True


async def async_get_config_and_coordinator(hass, platform_domain, discovery_info):
    """Get the config and coordinator for the platform from discovery."""
    shared_data = hass.data[DOMAIN][REST_DATA][discovery_info[REST_IDX]]
    conf = hass.data[DOMAIN][platform_domain][discovery_info[PLATFORM_IDX]]
    coordinator = shared_data[COORDINATOR]
    rest = shared_data[REST]
    if rest.data is None:
        await coordinator.async_request_refresh()
    return conf, coordinator, rest


def _rest_coordinator(hass, rest, resource_template, update_interval):
    """Wrap a DataUpdateCoordinator around the rest object."""
    if resource_template:

        async def _async_refresh_with_resource_template():
            rest.set_url(resource_template.async_render(parse_result=False))
            await rest.async_update()

        update_method = _async_refresh_with_resource_template
    else:
        update_method = rest.async_update

    return DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="rest data",
        update_method=update_method,
        update_interval=update_interval,
    )


def create_rest_data_from_config(hass, config):
    """Create RestData from config."""
    resource = config.get(CONF_RESOURCE)
    resource_template = config.get(CONF_RESOURCE_TEMPLATE)
    method = config.get(CONF_METHOD)
    payload = config.get(CONF_PAYLOAD)
    verify_ssl = config.get(CONF_VERIFY_SSL)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    headers = config.get(CONF_HEADERS)
    params = config.get(CONF_PARAMS)
    timeout = config.get(CONF_TIMEOUT)

    if resource_template is not None:
        resource_template.hass = hass
        resource = resource_template.async_render(parse_result=False)

    if username and password:
        if config.get(CONF_AUTHENTICATION) == HTTP_DIGEST_AUTHENTICATION:
            auth = httpx.DigestAuth(username, password)
        else:
            auth = (username, password)
    else:
        auth = None

    return RestData(
        hass, method, resource, auth, headers, params, payload, verify_ssl, timeout
    )
