"""The rest component."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_PAYLOAD_TEMPLATE, COORDINATOR, DOMAIN, PLATFORM_IDX, REST_IDX
from .coordinator import RestCoordinator
from .data import RestData
from .schema import CONFIG_SCHEMA, RESOURCE_SCHEMA
from .services import async_setup_services
from .util import (
    async_process_config,
    async_setup_shared_data,
    create_rest_data_from_config,
)

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "CONFIG_SCHEMA",
    "CONF_PAYLOAD_TEMPLATE",
    "DOMAIN",
    "RESOURCE_SCHEMA",
    "RestData",
    "create_rest_data_from_config",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the rest platforms."""
    async_setup_shared_data(hass)
    async_setup_services(hass)

    return await async_process_config(hass, config)


async def async_get_config_and_coordinator(
    hass: HomeAssistant, platform_domain: str, discovery_info: DiscoveryInfoType
) -> tuple[ConfigType, RestCoordinator, RestData]:
    """Get the config and coordinator for the platform from discovery."""
    coordinator: RestCoordinator = hass.data[DOMAIN][COORDINATOR][
        discovery_info[REST_IDX]
    ]
    conf: ConfigType = hass.data[DOMAIN][platform_domain][discovery_info[PLATFORM_IDX]]
    if coordinator.rest.data is None:
        await coordinator.async_request_refresh()
    return conf, coordinator, coordinator.rest
