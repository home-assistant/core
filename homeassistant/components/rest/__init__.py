"""The rest component."""

import contextlib
import logging

import probatio

from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.reload import (
    async_integration_yaml_config,
    async_reload_integration_platforms,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_PAYLOAD_TEMPLATE,  # noqa: F401
    COORDINATOR,
    DOMAIN,
    PLATFORM_IDX,
    PLATFORMS,
    REST_IDX,
)
from .coordinator import RestCoordinator
from .data import RestData
from .schema import CONFIG_SCHEMA, RESOURCE_SCHEMA  # noqa: F401
from .util import (
    async_process_config,
    async_setup_shared_data,
    create_rest_data_from_config,  # noqa: F401
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the rest platforms."""
    async_setup_shared_data(hass)

    async def reload_service_handler(service: ServiceCall) -> None:
        """Remove all user-defined groups and load new ones from config."""
        conf = None
        # pylint: disable-next=home-assistant-action-swallowed-exception
        with contextlib.suppress(HomeAssistantError):
            conf = await async_integration_yaml_config(hass, DOMAIN)
        if conf is None:
            return
        await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)
        async_setup_shared_data(hass)
        await async_process_config(hass, conf)

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=probatio.Schema({})
    )

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
