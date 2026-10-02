"""Services for the Portainer integration."""

from datetime import timedelta
from enum import StrEnum

import probatio

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    service,
)

from .const import DOMAIN
from .coordinator import PortainerConfigEntry
from .util import async_call_portainer


class PortainerService(StrEnum):
    """Store keys for Portainer services."""

    PRUNE_IMAGES = "prune_images"
    PRUNE_BUILD_CACHE = "prune_build_cache"
    RECREATE_CONTAINER = "recreate_container"


class PortainerServiceArgument(StrEnum):
    """Store keys for Portainer service arguments."""

    ALL = "all"
    UNTIL = "until"
    DANGLING = "dangling"
    TIMEOUT = "timeout"
    PULL_IMAGE = "pull_image"
    CONTAINER_DEVICE_ID = "container_device_id"


SERVICE_PRUNE_IMAGES_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_DEVICE_ID): cv.string,
        probatio.Optional(PortainerServiceArgument.UNTIL): probatio.All(
            cv.time_period, probatio.Range(min=timedelta(minutes=1))
        ),
        probatio.Optional(PortainerServiceArgument.DANGLING): cv.boolean,
    },
)

SERVICE_PRUNE_BUILD_CACHE_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_DEVICE_ID): cv.string,
        probatio.Optional(PortainerServiceArgument.ALL, default=True): cv.boolean,
        probatio.Optional(PortainerServiceArgument.UNTIL): probatio.All(
            cv.time_period, probatio.Range(min=timedelta(minutes=1))
        ),
    },
)

SERVICE_RECREATE_CONTAINER_SCHEMA = probatio.Schema(
    {
        probatio.Required(PortainerServiceArgument.CONTAINER_DEVICE_ID): cv.string,
        probatio.Optional(PortainerServiceArgument.TIMEOUT): probatio.All(
            cv.time_period, probatio.Range(min=timedelta(minutes=1))
        ),
        probatio.Optional(PortainerServiceArgument.PULL_IMAGE): cv.boolean,
    }
)


@callback
def _async_get_device_and_entry(
    call: ServiceCall, device_id: str
) -> tuple[dr.AnyDeviceEntry, PortainerConfigEntry]:
    """Resolve and validate the device and Portainer config entry for a device ID."""
    entry: PortainerConfigEntry
    device, entry = service.async_get_device_and_config_entry(
        call.hass, DOMAIN, device_id
    )
    return device, entry


@callback
def _async_get_endpoint_id(
    device: dr.AnyDeviceEntry,
    config_entry: PortainerConfigEntry,
) -> int:
    """Get the endpoint ID from a device entry."""
    coordinator = config_entry.runtime_data

    for data in coordinator.data.values():
        if (
            DOMAIN,
            f"{config_entry.entry_id}_{data.endpoint.id}",
        ) in device.identifiers:
            return data.endpoint.id

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_target",
    )


@callback
def _async_get_container_and_endpoint_ids(
    device: dr.AnyDeviceEntry,
    config_entry: PortainerConfigEntry,
) -> tuple[int, str]:
    """Get the endpoint ID and container ID from a container device entry."""
    coordinator = config_entry.runtime_data

    for data in coordinator.data.values():
        for container_name, container_data in data.containers.items():
            if (
                DOMAIN,
                f"{config_entry.entry_id}_{data.endpoint.id}_{container_name}",
            ) in device.identifiers:
                return data.endpoint.id, container_data.container.id

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_target",
    )


async def prune_images(call: ServiceCall) -> None:
    """Prune unused images in Portainer, with more controls."""
    device, config_entry = _async_get_device_and_entry(call, call.data[ATTR_DEVICE_ID])
    coordinator = config_entry.runtime_data
    endpoint_id = _async_get_endpoint_id(device, config_entry)

    await async_call_portainer(
        coordinator,
        coordinator.portainer.images_prune(
            endpoint_id=endpoint_id,
            until=call.data.get(PortainerServiceArgument.UNTIL),
            dangling=call.data.get(PortainerServiceArgument.DANGLING, False),
        ),
    )


async def prune_build_cache(call: ServiceCall) -> None:
    """Prune the build cache in Portainer, with more controls."""
    device, config_entry = _async_get_device_and_entry(call, call.data[ATTR_DEVICE_ID])
    coordinator = config_entry.runtime_data
    endpoint_id = _async_get_endpoint_id(device, config_entry)

    await async_call_portainer(
        coordinator,
        coordinator.portainer.prune_build_cache(
            endpoint_id,
            all_cache=call.data[PortainerServiceArgument.ALL],
            until=call.data.get(PortainerServiceArgument.UNTIL),
        ),
    )


async def recreate_container(call: ServiceCall) -> None:
    """Recreate a container in Portainer, with more controls."""
    device, config_entry = _async_get_device_and_entry(
        call, call.data[PortainerServiceArgument.CONTAINER_DEVICE_ID]
    )
    coordinator = config_entry.runtime_data
    endpoint_id, container_id = _async_get_container_and_endpoint_ids(
        device, config_entry
    )
    timeout: timedelta | None = call.data.get(PortainerServiceArgument.TIMEOUT)

    await async_call_portainer(
        coordinator,
        coordinator.portainer.container_recreate(
            endpoint_id=endpoint_id,
            container_id=container_id,
            **({"timeout": timeout} if timeout is not None else {}),
            pull_image=call.data.get(PortainerServiceArgument.PULL_IMAGE, False),
        ),
    )

    await coordinator.async_request_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    service.async_register_admin_service(
        hass,
        DOMAIN,
        PortainerService.PRUNE_IMAGES,
        prune_images,
        SERVICE_PRUNE_IMAGES_SCHEMA,
    )

    service.async_register_admin_service(
        hass,
        DOMAIN,
        PortainerService.PRUNE_BUILD_CACHE,
        prune_build_cache,
        SERVICE_PRUNE_BUILD_CACHE_SCHEMA,
    )

    service.async_register_admin_service(
        hass,
        DOMAIN,
        PortainerService.RECREATE_CONTAINER,
        recreate_container,
        SERVICE_RECREATE_CONTAINER_SCHEMA,
    )
