"""The rest component."""

import asyncio
from collections.abc import Coroutine
import contextlib
from dataclasses import dataclass
from datetime import timedelta
import logging
from types import MappingProxyType
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
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
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import discovery, template
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.reload import (
    async_integration_yaml_config,
    async_reload_integration_platforms,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.async_ import create_eager_task

from .const import (
    CONF_ENCODING,
    CONF_PAYLOAD_TEMPLATE,
    CONF_SSL_CIPHER_LIST,
    CONF_SSL_SECTION,
    CONFIG_ENTRY_PLATFORMS,
    COORDINATOR,
    DEFAULT_SSL_CIPHER_LIST,
    DOMAIN,
    PLATFORM_IDX,
    REST,
    REST_DATA,
    REST_IDX,
)
from .data import RestData
from .schema import CONFIG_SCHEMA, RESOURCE_SCHEMA  # noqa: F401

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NOTIFY,
    Platform.SENSOR,
    Platform.SWITCH,
]

COORDINATOR_AWARE_PLATFORMS = [SENSOR_DOMAIN, BINARY_SENSOR_DOMAIN]


@dataclass
class RestRuntimeData:
    """Hold the runtime data for the integration."""

    coordinator: DataUpdateCoordinator[None]
    rest: RestData


RestConfigEntry = ConfigEntry[RestRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the rest platforms."""
    _async_setup_shared_data(hass)

    async def reload_service_handler(service: ServiceCall) -> None:
        """Remove all user-defined groups and load new ones from config."""
        conf = None
        # pylint: disable-next=home-assistant-action-swallowed-exception
        with contextlib.suppress(HomeAssistantError):
            conf = await async_integration_yaml_config(hass, DOMAIN)
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
def _async_setup_shared_data(hass: HomeAssistant) -> None:
    """Create shared data for platform config and rest coordinators."""
    hass.data[DOMAIN] = {key: [] for key in (REST_DATA, *COORDINATOR_AWARE_PLATFORMS)}  # pylint: disable=home-assistant-use-runtime-data


async def async_setup_entry(hass: HomeAssistant, config_entry: RestConfigEntry) -> bool:
    """Setup config entry."""

    rest: RestData = create_rest_data_from_config_entry(hass, config_entry.data)

    await rest.async_update()

    if rest.last_exception:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="endpoint_error",
            translation_placeholders={"error_message": str(rest.last_exception)},
        ) from rest.last_exception

    resource_template: template.Template = template.Template(
        config_entry.data[CONF_RESOURCE], hass
    )
    payload_template: template.Template | None = (
        template.Template(config_entry.data[CONF_PAYLOAD], hass)
        if config_entry.data.get(CONF_PAYLOAD)
        else None
    )

    coordinator: DataUpdateCoordinator[None] = _rest_coordinator(
        hass,
        rest,
        resource_template,
        payload_template,
        DEFAULT_SCAN_INTERVAL,
    )

    config_entry.runtime_data = RestRuntimeData(coordinator, rest)

    await hass.config_entries.async_forward_entry_setups(
        config_entry, CONFIG_ENTRY_PLATFORMS
    )

    config_entry.async_on_unload(config_entry.add_update_listener(_async_entry_updated))

    return True


async def _async_entry_updated(
    hass: HomeAssistant, config_entry: RestConfigEntry
) -> None:
    hass.config_entries.async_schedule_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: RestConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(
        entry, CONFIG_ENTRY_PLATFORMS
    )
    if unloaded:
        await entry.runtime_data.coordinator.async_shutdown()
    return unloaded


async def _async_process_config(hass: HomeAssistant, config: ConfigType) -> bool:
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
        coordinator = _rest_coordinator(
            hass, rest, resource_template, payload_template, scan_interval
        )
        refresh_coroutines.append(coordinator.async_refresh())
        hass.data[DOMAIN][REST_DATA].append({REST: rest, COORDINATOR: coordinator})  # pylint: disable=home-assistant-use-runtime-data

        for platform_domain in COORDINATOR_AWARE_PLATFORMS:
            if platform_domain not in conf:
                continue

            for platform_conf in conf[platform_domain]:
                hass.data[DOMAIN][platform_domain].append(platform_conf)  # pylint: disable=home-assistant-use-runtime-data
                platform_idx = len(hass.data[DOMAIN][platform_domain]) - 1  # pylint: disable=home-assistant-use-runtime-data

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


async def async_get_config_and_coordinator(
    hass: HomeAssistant, platform_domain: str, discovery_info: DiscoveryInfoType
) -> tuple[ConfigType, DataUpdateCoordinator[None], RestData]:
    """Get the config and coordinator for the platform from discovery."""
    shared_data = hass.data[DOMAIN][REST_DATA][discovery_info[REST_IDX]]  # pylint: disable=home-assistant-use-runtime-data
    conf: ConfigType = hass.data[DOMAIN][platform_domain][discovery_info[PLATFORM_IDX]]  # pylint: disable=home-assistant-use-runtime-data
    coordinator: DataUpdateCoordinator[None] = shared_data[COORDINATOR]
    rest: RestData = shared_data[REST]
    if rest.data is None:
        await coordinator.async_request_refresh()
    return conf, coordinator, rest


def _rest_coordinator(
    hass: HomeAssistant,
    rest: RestData,
    resource_template: template.Template | None,
    payload_template: template.Template | None,
    update_interval: timedelta,
) -> DataUpdateCoordinator[None]:
    """Wrap a DataUpdateCoordinator around the rest object."""
    if resource_template or payload_template:

        async def _async_refresh_with_templates() -> None:
            if resource_template:
                rest.set_url(resource_template.async_render(parse_result=False))
            if payload_template:
                rest.set_payload(payload_template.async_render(parse_result=False))
            await rest.async_update()

        update_method = _async_refresh_with_templates
    else:
        update_method = rest.async_update

    return DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=None,
        name="rest data",
        update_method=update_method,
        update_interval=update_interval,
    )


def create_rest_data_from_config_entry(
    hass: HomeAssistant, config: dict[str, Any] | MappingProxyType[str, Any]
) -> RestData:
    """Create RestData from user input or config entry data."""
    mutable_config: dict[str, Any] = {**config}
    mutable_config[CONF_RESOURCE_TEMPLATE] = mutable_config.pop(CONF_RESOURCE)
    if mutable_config.get(CONF_PAYLOAD):
        mutable_config[CONF_PAYLOAD_TEMPLATE] = mutable_config.pop(CONF_PAYLOAD)
    for key in (CONF_PARAMS, CONF_HEADERS):
        if key in mutable_config:
            mutable_config[key] = {
                param["key"]: param["value"] for param in mutable_config[key]
            }
    # Flatten to match .yaml format
    ssl: dict[str, Any] = mutable_config.pop(CONF_SSL_SECTION)
    auth: dict[str, Any] = mutable_config.pop(CONF_AUTHENTICATION)
    return create_rest_data_from_config(
        hass,
        vol.Schema(RESOURCE_SCHEMA, extra=vol.REMOVE_EXTRA)(
            mutable_config | ssl | auth
        ),  # To convert templates
    )


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
